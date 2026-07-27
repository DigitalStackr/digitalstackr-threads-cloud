"""
Instagram posting via the Meta Graph API (Content Publishing API).

Runs off the SAME Meta app + Page token flow as Facebook — the IG account is a
Business account linked to the DigitalStackr Page, so the Page access token
(with instagram_basic + instagram_content_publish) is what authorizes publishing.

Env vars (set by GitHub Actions from repo secrets):
  FB_PAGE_TOKEN  — Page access token, must carry the two instagram_* scopes
  IG_USER_ID     — the instagram_business_account id linked to the Page

Publishing is ALWAYS 2-step (3 for video, because encoding is async):
  1. create a media container   POST /{ig-user-id}/media
  2. (video only) poll it       GET  /{container-id}?fields=status_code
  3. publish it                 POST /{ig-user-id}/media_publish

Supported content:
  REELS    — video_url  (the primary IG format for this brand)
  IMAGE    — image_url
  CAROUSEL — list of image/video urls (2-10 items)

Media is passed by PUBLIC URL (raw.githubusercontent.com from this repo), the
same approach as Facebook photos — no binary upload needed, and it keeps the
"real images only, from the repo" rule intact.
"""
import os
import time

import requests

GRAPH = "https://graph.facebook.com/v21.0"

# Video containers encode asynchronously. Reels of a few MB are usually ready in
# 10-40s; we allow generous headroom before giving up so a slow encode doesn't
# turn into a false failure (the scheduler's self-heal would retry it anyway).
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 300


def _creds():
    token = os.environ.get("FB_PAGE_TOKEN")
    ig_user = os.environ.get("IG_USER_ID")
    if not token or not ig_user:
        raise RuntimeError("Missing FB_PAGE_TOKEN or IG_USER_ID environment variable")
    return token, ig_user


def _call(method, endpoint, payload, timeout=60):
    fn = requests.post if method == "POST" else requests.get
    kwargs = {"data": payload} if method == "POST" else {"params": payload}
    r = fn(endpoint, timeout=timeout, **kwargs)
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"Instagram API returned non-JSON (status {r.status_code})")
    if r.status_code >= 300 or "error" in data:
        raise RuntimeError(f"Instagram API error: {data.get('error', data)}")
    return data


def _wait_for_container(container_id: str, token: str) -> None:
    """Block until an async (video) container finishes encoding. Raises on ERROR."""
    deadline = time.time() + POLL_TIMEOUT_SEC
    last = None
    while time.time() < deadline:
        data = _call("GET", f"{GRAPH}/{container_id}",
                     {"fields": "status_code,status", "access_token": token}, timeout=30)
        last = data.get("status_code")
        if last == "FINISHED":
            return
        if last in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram container {container_id} failed: "
                               f"{last} — {data.get('status')}")
        time.sleep(POLL_INTERVAL_SEC)
    raise RuntimeError(f"Instagram container {container_id} not ready after "
                       f"{POLL_TIMEOUT_SEC}s (last status {last})")


def _create_container(ig_user: str, token: str, payload: dict, is_video: bool) -> str:
    payload["access_token"] = token
    data = _call("POST", f"{GRAPH}/{ig_user}/media", payload)
    container_id = data.get("id")
    if not container_id:
        raise RuntimeError(f"Instagram did not return a container id: {data}")
    if is_video:
        _wait_for_container(container_id, token)
    return container_id


def post_instagram(text: str, image_url: str = None, video_url: str = None,
                   carousel_urls: list = None, share_to_feed: bool = True) -> str:
    """Publish to Instagram. Returns the published media id.

    Exactly one of video_url / image_url / carousel_urls must be given —
    Instagram cannot publish a text-only post.
    """
    token, ig_user = _creds()
    caption = text or ""

    if carousel_urls:
        if not 2 <= len(carousel_urls) <= 10:
            raise RuntimeError(f"IG carousel needs 2-10 items, got {len(carousel_urls)}")
        children = []
        for url in carousel_urls:
            is_video = _looks_like_video(url)
            item = {"is_carousel_item": "true"}
            if is_video:
                item["media_type"] = "VIDEO"
                item["video_url"] = url
            else:
                item["image_url"] = url
            children.append(_create_container(ig_user, token, item, is_video))
        creation_id = _create_container(
            ig_user, token,
            {"media_type": "CAROUSEL", "caption": caption, "children": ",".join(children)},
            is_video=False,
        )

    elif video_url:
        creation_id = _create_container(
            ig_user, token,
            {"media_type": "REELS", "video_url": video_url, "caption": caption,
             "share_to_feed": "true" if share_to_feed else "false"},
            is_video=True,
        )

    elif image_url:
        creation_id = _create_container(
            ig_user, token, {"image_url": image_url, "caption": caption}, is_video=False,
        )

    else:
        raise RuntimeError("Instagram requires media: pass video_url, image_url, or carousel_urls")

    data = _call("POST", f"{GRAPH}/{ig_user}/media_publish",
                 {"creation_id": creation_id, "access_token": token})
    media_id = data.get("id")
    if not media_id:
        raise RuntimeError(f"Instagram publish returned no media id: {data}")
    return media_id


def _looks_like_video(url: str) -> bool:
    return url.lower().split("?")[0].endswith((".mp4", ".mov"))


def quota_remaining() -> int:
    """Posts still allowed in the rolling 24h window (IG caps at 25)."""
    token, ig_user = _creds()
    data = _call("GET", f"{GRAPH}/{ig_user}/content_publishing_limit",
                 {"fields": "config,quota_usage", "access_token": token}, timeout=30)
    row = (data.get("data") or [{}])[0]
    total = (row.get("config") or {}).get("quota_total", 25)
    return int(total) - int(row.get("quota_usage", 0))
