"""
X (Twitter) posting via API v2, with a hard cost guard.

WHY THE URL GUARD EXISTS — this is the whole point of this module:
X's pay-per-use pricing (default since 2026-02-06, verified 2026-07-30) charges
    $0.015  per post
    $0.20   per post THAT CONTAINS A LINK      <- 13x more expensive
At ~180 posts/month that is $2.70 vs $36.00. So a URL must never reach the post
body by accident. This module strips any URL out of the body and publishes it as
a threaded REPLY instead (the same "link in the first comment" pattern we already
use on Threads), which keeps every post at the $0.015 rate.

Set X_URL_POLICY=refuse to make a URL a hard error instead of moving it.

Auth: OAuth 1.0a user context. The Bearer Token is app-only and CANNOT post — you
need all four of API key/secret + access token/secret.

Env vars (from repo secrets):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
  X_URL_POLICY   — "reply" (default) or "refuse"
"""
import os
import re

import requests
from requests_oauthlib import OAuth1

API = "https://api.twitter.com/2/tweets"
MAX_CHARS = 280

# Matches explicit URLs and bare domains, because X auto-links bare domains too
# and those bill at the link rate just the same.
URL_RE = re.compile(
    r"(?:https?://\S+)"
    r"|(?:\bwww\.\S+)"
    r"|(?:\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|co|me|gg|ai|app|shop|store|link|bio)"
    r"(?:/\S*)?\b)",
    re.I,
)


def _auth():
    key = os.environ.get("X_API_KEY")
    secret = os.environ.get("X_API_SECRET")
    token = os.environ.get("X_ACCESS_TOKEN")
    token_secret = os.environ.get("X_ACCESS_SECRET")
    missing = [n for n, v in [("X_API_KEY", key), ("X_API_SECRET", secret),
                              ("X_ACCESS_TOKEN", token), ("X_ACCESS_SECRET", token_secret)]
               if not v]
    if missing:
        raise RuntimeError(
            f"Missing {', '.join(missing)}. Note the Bearer Token is app-only and "
            f"cannot post — user-context OAuth 1.0a needs all four values."
        )
    return OAuth1(key, secret, token, token_secret)


def extract_urls(text: str) -> list:
    return URL_RE.findall(text or "")


def split_urls(text: str):
    """Return (body_without_urls, [urls]). Body is tidied so removal leaves no
    dangling punctuation or double spaces."""
    urls = extract_urls(text)
    if not urls:
        return text, []
    body = URL_RE.sub("", text or "")
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"[ \t]+([.,!?])", r"\1", body)
    body = re.sub(r"(?m)[ \t]+$", "", body)
    return body.strip(), urls


def _create(auth, payload: dict) -> str:
    r = requests.post(API, json=payload, auth=auth, timeout=60)
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"X API returned non-JSON (status {r.status_code})")
    if r.status_code >= 300 or "errors" in data or "error" in data:
        # 403 here is usually "no billing set up" or missing write permission.
        raise RuntimeError(f"X API error (status {r.status_code}): "
                           f"{data.get('errors') or data.get('detail') or data}")
    tid = (data.get("data") or {}).get("id")
    if not tid:
        raise RuntimeError(f"X returned no tweet id: {data}")
    return tid


def upload_media(auth, image_url: str) -> str:
    """Fetch a repo screenshot and upload it to X. Returns a media_id string.

    WHY THIS EXISTS: X posts used to go out text-only, so a caption reading
    "$224.52 today" published with NOTHING backing it - a bare income claim, and a
    straight violation of the rule that every figure must match an attached
    screenshot. Text-only was never a decision, just an unbuilt flow.

    Billing note: the $0.20 surcharge is specifically for a LINK IN THE BODY, not
    for media, so attaching an image should leave a post at the $0.015 base rate.
    'Should' - confirm against the billing dashboard after the first image post
    before queueing a week of them.
    """
    img = requests.get(image_url, timeout=60)
    img.raise_for_status()
    r = requests.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        files={"media": img.content},
        auth=auth,
        timeout=120,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"X media upload failed (status {r.status_code}): {r.text[:300]}")
    media_id = (r.json() or {}).get("media_id_string")
    if not media_id:
        raise RuntimeError(f"X media upload returned no media_id: {r.text[:300]}")
    return media_id


def post_x(text: str, image_url: str = None) -> str:
    """Publish to X. Returns the tweet id of the main post.

    Any URL is moved out of the body into a threaded reply so the post bills at
    $0.015 instead of $0.20. image_url, when given, is uploaded and attached.
    """
    auth = _auth()
    policy = os.environ.get("X_URL_POLICY", "reply").lower()

    body, urls = split_urls(text or "")

    if urls and policy == "refuse":
        raise RuntimeError(
            f"X post contains {len(urls)} URL(s) and X_URL_POLICY=refuse. "
            f"A link in the body costs $0.20 instead of $0.015. URLs: {urls}"
        )

    if len(body) > MAX_CHARS:
        raise RuntimeError(f"X post body is {len(body)} chars; max {MAX_CHARS}")
    if not body:
        raise RuntimeError("X post body is empty after removing URLs")

    payload = {"text": body}
    if image_url:
        # Deliberately NOT wrapped in try/except: if the screenshot can't be
        # attached, the post must fail rather than publish a figure with no proof.
        payload["media"] = {"media_ids": [upload_media(auth, image_url)]}

    tweet_id = _create(auth, payload)

    # Link goes in a reply, never the body — this is the cost guard doing its job.
    if urls:
        reply = " ".join(urls)[:MAX_CHARS]
        try:
            _create(auth, {"text": reply, "reply": {"in_reply_to_tweet_id": tweet_id}})
            print(f"X: link moved to reply on {tweet_id} (saved $0.185)", flush=True)
        except Exception as e:
            # The main post is already live; a failed reply must not fail the entry.
            print(f"X: WARNING main post {tweet_id} published but link reply failed: {e}",
                  flush=True)

    return tweet_id


def estimate_cost(text: str) -> float:
    """What this post will actually bill, after the guard runs."""
    body, urls = split_urls(text or "")
    return 0.015 + (0.015 if urls else 0.0)   # main post + optional link reply
