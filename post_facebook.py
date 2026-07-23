"""
Facebook Page posting via Meta Graph API.

Publishes to a Facebook Page you own, using a NON-EXPIRING Page access token
(derived from a long-lived user token — see README/setup notes).

Env vars (set by GitHub Actions from repo secrets):
  FB_PAGE_TOKEN  — the Page access token
  FB_PAGE_ID     — the numeric Page id

Text posts  -> POST /{page-id}/feed    (message)
Photo posts -> POST /{page-id}/photos  (public image url + caption)

We pass images by public URL (the repo's raw.githubusercontent image URL),
so no binary upload is needed — same "real images only from images/ folder" rule.
"""
import os
import requests

GRAPH = "https://graph.facebook.com/v21.0"


def _creds():
    token = os.environ.get("FB_PAGE_TOKEN")
    page = os.environ.get("FB_PAGE_ID")
    if not token or not page:
        raise RuntimeError("Missing FB_PAGE_TOKEN or FB_PAGE_ID environment variable")
    return token, page


def post_facebook(text: str, image_url: str = None) -> str:
    """Publish to the Facebook Page. Returns the created post id."""
    token, page = _creds()

    if image_url:
        endpoint = f"{GRAPH}/{page}/photos"
        payload = {"url": image_url, "caption": text or "", "access_token": token}
    else:
        endpoint = f"{GRAPH}/{page}/feed"
        payload = {"message": text, "access_token": token}

    r = requests.post(endpoint, data=payload, timeout=60)
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"Facebook API returned non-JSON (status {r.status_code})")

    if r.status_code >= 300 or "error" in data:
        raise RuntimeError(f"Facebook API error: {data.get('error', data)}")

    # /feed returns {"id": "PAGEID_POSTID"}; /photos returns {"id": "...", "post_id": "..."}
    return data.get("post_id") or data.get("id")


def delete_facebook(post_id: str) -> bool:
    """Delete a post (used for cleaning up test posts). Returns True on success."""
    token, _ = _creds()
    r = requests.delete(f"{GRAPH}/{post_id}", params={"access_token": token}, timeout=30)
    try:
        data = r.json()
    except ValueError:
        return False
    return bool(data.get("success")) or r.status_code < 300
