"""
TikTok posting via the Content Posting API.

VERIFIED AGAINST TIKTOK'S DOCS 2026-07-27 — the constraints below are real and
each one shaped this implementation:

1. AUDIT GATE. An unaudited API client can only publish SELF_ONLY (private), and
   every authorizing account must itself be private at the time of posting.
   Public posting requires passing TikTok's audit (2-4 weeks, multiple rounds).
   We therefore ALWAYS ask creator_info for the allowed privacy levels and pick a
   permitted one instead of assuming PUBLIC_TO_EVERYONE — posting with a level the
   account doesn't allow is a hard error.

2. TOKEN LIFECYCLE. access_token lives 24h; refresh_token lives 365 days and MAY
   ROTATE on every refresh ("You must use the newly-returned token if the value is
   different"). So every run refreshes, and a rotated refresh token MUST be
   persisted or the next run is locked out — see _persist_refresh_token().

3. UPLOAD METHOD. Videos use FILE_UPLOAD: TikTok hands back an upload_url and we
   PUT the bytes. We deliberately do NOT use PULL_FROM_URL, because that requires
   verifying ownership of the hosting domain and we serve media from
   raw.githubusercontent.com, which we can't verify.
   (Photo carousels are PULL_FROM_URL-ONLY, so they stay blocked until a domain we
   control — e.g. GitHub Pages — is verified. See post_tiktok_photos().)

4. RATE LIMIT. 6 requests/minute per access token on the init endpoints.

Env vars (from repo secrets):
  TIKTOK_CLIENT_KEY
  TIKTOK_CLIENT_SECRET
  TIKTOK_REFRESH_TOKEN     — rotated automatically; see persistence note
  GH_SECRETS_PAT           — optional; lets a rotated refresh token be written back
"""
import os
import time

import requests

OAUTH_URL = "https://open.tiktokapis.com/v2/oauth/token/"
API = "https://open.tiktokapis.com/v2"

# Poll the publish status until TikTok finishes processing the upload.
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 300

# Chunk size for FILE_UPLOAD. TikTok wants 5MB-64MB chunks; a single chunk is
# simplest and valid for the short reels this brand posts (<50MB by repo policy).
MAX_SINGLE_CHUNK = 64 * 1024 * 1024

# Preference order when the account allows several privacy levels. An unaudited
# client will only ever be offered SELF_ONLY, which is the correct fallback.
PRIVACY_PREFERENCE = [
    "PUBLIC_TO_EVERYONE",
    "FOLLOWER_OF_CREATOR",
    "MUTUAL_FOLLOW_FRIENDS",
    "SELF_ONLY",
]


def _creds():
    key = os.environ.get("TIKTOK_CLIENT_KEY")
    secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    refresh = os.environ.get("TIKTOK_REFRESH_TOKEN")
    if not key or not secret or not refresh:
        raise RuntimeError(
            "Missing TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REFRESH_TOKEN"
        )
    return key, secret, refresh


def _persist_refresh_token(new_token: str) -> None:
    """Write a rotated refresh token back into the repo secret.

    TikTok may hand back a different refresh_token on any refresh. If we don't
    store it, the NEXT scheduler run authenticates with a dead token and TikTok
    posting silently stops until someone re-does OAuth by hand. This is the most
    likely long-term failure mode of the whole TikTok integration, so it fails
    LOUDLY rather than silently when it can't persist.
    """
    pat = os.environ.get("GH_SECRETS_PAT")
    if not pat:
        raise RuntimeError(
            "TikTok rotated the refresh token but GH_SECRETS_PAT is not set, so it "
            "cannot be saved. The next run WILL fail to authenticate. Store the new "
            "refresh token in the TIKTOK_REFRESH_TOKEN secret manually."
        )
    # Imported lazily: only this path needs crypto, and only inside Actions.
    import base64
    from nacl import encoding, public

    repo = os.environ.get("GITHUB_REPOSITORY", "DigitalStackr/digitalstackr-threads-cloud")
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                     headers=headers, timeout=30)
    r.raise_for_status()
    keydata = r.json()
    sealed = public.SealedBox(
        public.PublicKey(keydata["key"].encode(), encoding.Base64Encoder())
    ).encrypt(new_token.encode())
    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/TIKTOK_REFRESH_TOKEN",
        headers=headers,
        json={"encrypted_value": base64.b64encode(sealed).decode(),
              "key_id": keydata["key_id"]},
        timeout=30,
    )
    if r.status_code not in (201, 204):
        raise RuntimeError(f"Failed to persist rotated TikTok refresh token: "
                           f"{r.status_code} {r.text[:200]}")
    print("TikTok: refresh token rotated and saved to repo secret", flush=True)


def get_access_token() -> str:
    """Exchange the stored refresh token for a 24h access token (handling rotation)."""
    key, secret, refresh = _creds()
    r = requests.post(
        OAUTH_URL,
        data={"client_key": key, "client_secret": secret,
              "grant_type": "refresh_token", "refresh_token": refresh},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    data = r.json()
    if r.status_code >= 300 or "error" in data and data.get("error"):
        raise RuntimeError(f"TikTok token refresh failed: {data}")
    access = data.get("access_token")
    if not access:
        raise RuntimeError(f"TikTok token refresh returned no access_token: {data}")

    new_refresh = data.get("refresh_token")
    if new_refresh and new_refresh != refresh:
        _persist_refresh_token(new_refresh)
    return access


def _post(path: str, token: str, body: dict, timeout: int = 60) -> dict:
    r = requests.post(
        f"{API}{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        timeout=timeout,
    )
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"TikTok returned non-JSON (status {r.status_code})")
    err = (data.get("error") or {})
    if err and err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok API error on {path}: {err}")
    if r.status_code >= 300:
        raise RuntimeError(f"TikTok API HTTP {r.status_code} on {path}: {data}")
    return data.get("data", data)


def get_creator_info(token: str) -> dict:
    """Required before posting: returns the privacy levels this account allows."""
    return _post("/post/publish/creator_info/query/", token, {})


def _choose_privacy(creator_info: dict, requested: str = None) -> str:
    allowed = creator_info.get("privacy_level_options") or []
    if not allowed:
        raise RuntimeError(f"TikTok returned no privacy_level_options: {creator_info}")
    if requested:
        if requested not in allowed:
            raise RuntimeError(
                f"Requested privacy '{requested}' not allowed for this account "
                f"(allowed: {allowed}). Unaudited clients only get SELF_ONLY."
            )
        return requested
    for level in PRIVACY_PREFERENCE:
        if level in allowed:
            return level
    return allowed[0]


def _wait_for_publish(publish_id: str, token: str) -> str:
    deadline = time.time() + POLL_TIMEOUT_SEC
    last = None
    while time.time() < deadline:
        data = _post("/post/publish/status/fetch/", token, {"publish_id": publish_id}, timeout=30)
        last = data.get("status")
        if last == "PUBLISH_COMPLETE":
            return publish_id
        if last in ("FAILED", "PUBLISH_FAILED"):
            raise RuntimeError(f"TikTok publish failed: {data}")
        time.sleep(POLL_INTERVAL_SEC)
    raise RuntimeError(f"TikTok publish {publish_id} not complete after "
                       f"{POLL_TIMEOUT_SEC}s (last status {last})")


def post_tiktok(text: str, video_path: str, privacy_level: str = None,
                disable_comment: bool = False) -> str:
    """Publish a video to TikTok from a LOCAL file path. Returns the publish_id.

    video_path is a real file on the runner (the repo is checked out), because
    TikTok's FILE_UPLOAD wants the bytes — it can't pull from our GitHub raw URLs.
    """
    if not os.path.isfile(video_path):
        raise RuntimeError(f"TikTok video file not found: {video_path}")
    size = os.path.getsize(video_path)
    if size == 0:
        raise RuntimeError(f"TikTok video file is empty: {video_path}")
    if size > MAX_SINGLE_CHUNK:
        raise RuntimeError(
            f"TikTok video is {size} bytes; this uploader sends a single chunk "
            f"(max {MAX_SINGLE_CHUNK}). Split it or add chunked upload."
        )

    token = get_access_token()
    creator = get_creator_info(token)
    privacy = _choose_privacy(creator, privacy_level)

    init = _post("/post/publish/video/init/", token, {
        "post_info": {
            "title": (text or "")[:2200],
            "privacy_level": privacy,
            "disable_comment": bool(disable_comment),
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        },
    })

    publish_id = init.get("publish_id")
    upload_url = init.get("upload_url")
    if not publish_id or not upload_url:
        raise RuntimeError(f"TikTok init returned no publish_id/upload_url: {init}")

    with open(video_path, "rb") as f:
        body = f.read()
    put = requests.put(
        upload_url,
        data=body,
        headers={"Content-Type": "video/mp4",
                 "Content-Length": str(size),
                 "Content-Range": f"bytes 0-{size - 1}/{size}"},
        timeout=600,
    )
    if put.status_code >= 300:
        raise RuntimeError(f"TikTok upload failed: HTTP {put.status_code} {put.text[:200]}")

    _wait_for_publish(publish_id, token)
    print(f"TikTok: published {publish_id} with privacy {privacy}", flush=True)
    return publish_id


def post_tiktok_photos(text: str, image_urls: list, privacy_level: str = None) -> str:
    """Publish a photo carousel (2-35 images).

    BLOCKED until a domain we control is verified with TikTok: photo posts accept
    ONLY PULL_FROM_URL, and TikTok rejects unverified hosts with
    'url_ownership_unverified'. raw.githubusercontent.com can't be verified — the
    planned fix is to serve images from GitHub Pages and verify that prefix.
    """
    if not 2 <= len(image_urls) <= 35:
        raise RuntimeError(f"TikTok carousel needs 2-35 images, got {len(image_urls)}")
    token = get_access_token()
    creator = get_creator_info(token)
    privacy = _choose_privacy(creator, privacy_level)

    init = _post("/post/publish/content/init/", token, {
        "post_info": {"title": (text or "")[:90], "description": (text or "")[:4000],
                      "privacy_level": privacy},
        "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0,
                        "photo_images": image_urls},
        "post_mode": "DIRECT_POST",
        "media_type": "PHOTO",
    })
    publish_id = init.get("publish_id")
    if not publish_id:
        raise RuntimeError(f"TikTok photo init returned no publish_id: {init}")
    _wait_for_publish(publish_id, token)
    return publish_id
