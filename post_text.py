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


def post_text(account: str, text: str) -> str:
    """Post text-only to Threads. Returns the published thread ID."""
    token = get_token(account)

    # Step 1: create media container
    r = requests.post(
        "https://graph.threads.net/v1.0/me/threads",
        data={
            "media_type": "TEXT",
            "text": text,
            "access_token": token,
        },
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
