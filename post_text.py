"""
Text post to Threads via official Meta API.
Reads token from environment variable (set by GitHub Actions from secrets).
"""
import os
import time
import requests


def get_token(account: str) -> str:
    key = f"{account}_TOKEN"
    token = os.environ.get(key)
    if not token:
        raise RuntimeError(f"Missing environment variable {key}")
    return token


def post_text(account: str, text: str, reply_to_id: str = None) -> str:
    """Post text-only to Threads. Returns the published thread ID.

    reply_to_id publishes this as a reply to an existing post of ours, which is how
    a long-form thread is built: part 1 is a normal post, parts 2..n each reply to
    the part before. Verified live 2026-08-05 - no extra scope is needed beyond the
    threads_content_publish we already hold.
    """
    token = get_token(account)

    payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": token,
    }
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

    # Step 1: create media container
    r = requests.post(
        "https://graph.threads.net/v1.0/me/threads",
        data=payload,
        timeout=30,
    )
    r.raise_for_status()
    creation_id = r.json()["id"]

    # Brief wait for container to be ready
    time.sleep(2)

    # Step 2: publish
    r = requests.post(
        "https://graph.threads.net/v1.0/me/threads_publish",
        data={
            "creation_id": creation_id,
            "access_token": token,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]
