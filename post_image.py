"""
Image post to Threads via official Meta API.
Reads image from repo's images/ folder, uploads to uguu.se for a public URL,
then posts via the Threads API.
"""
import os
import time
from pathlib import Path

import requests

IMAGES_DIR = Path(__file__).parent / "images"


def get_token(account: str) -> str:
    key = f"{account}_TOKEN"
    token = os.environ.get(key)
    if not token:
        raise RuntimeError(f"Missing environment variable {key}")
    return token


def upload_to_uguu(image_path: Path) -> str:
    """Upload local image to uguu.se, return public URL."""
    with open(image_path, "rb") as f:
        r = requests.post(
            "https://uguu.se/upload",
            files={"files[]": (image_path.name, f)},
            timeout=60,
        )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"uguu upload failed: {data}")
    return data["files"][0]["url"]


def post_image(account: str, text: str, image_filename: str) -> str:
    """Post image+text to Threads. Returns the published thread ID."""
    token = get_token(account)

    image_path = IMAGES_DIR / image_filename
    if not image_path.exists():
        raise RuntimeError(
            f"Image not found in repo: images/{image_filename} "
            f"(make sure you committed it to the repo's images/ folder)"
        )

    # Step 1: upload image to public host
    public_url = upload_to_uguu(image_path)

    # Step 2: create media container
    r = requests.post(
        "https://graph.threads.net/v1.0/me/threads",
        data={
            "media_type": "IMAGE",
            "image_url": public_url,
            "text": text,
            "access_token": token,
        },
        timeout=30,
    )
    r.raise_for_status()
    creation_id = r.json()["id"]

    # Image containers need ~30s for Meta to fetch + process
    time.sleep(30)

    # Step 3: publish
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
