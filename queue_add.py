"""
Adds a post to queue.json.
Called by the GitHub Actions workflow_dispatch form ("Add Post to Queue").

Usage:
    python queue_add.py <account> <text> <YYYY-MM-DD HH:MM Berlin time> [image_filename]
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

QUEUE_PATH = Path(__file__).parent / "queue.json"
BERLIN = ZoneInfo("Europe/Berlin")


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: queue_add.py <account> <text> <YYYY-MM-DD HH:MM> [image_filename]")
        sys.exit(1)

    account = sys.argv[1].strip()
    text = sys.argv[2]
    time_str = sys.argv[3].strip()
    image = sys.argv[4].strip() if len(sys.argv) > 4 and sys.argv[4].strip() else None

    if account not in ("MAIN", "TDS"):
        print(f"Account must be MAIN or TDS, got: {account}")
        sys.exit(1)

    try:
        local_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=BERLIN)
    except ValueError:
        print(f"Time must be 'YYYY-MM-DD HH:MM' (24h Berlin time). Got: {time_str}")
        sys.exit(1)

    iso_time = local_dt.isoformat()

    queue = []
    if QUEUE_PATH.exists():
        raw = QUEUE_PATH.read_text(encoding="utf-8").strip()
        if raw and raw != "[]":
            queue = json.loads(raw)

    next_id = max((e.get("id", 0) for e in queue), default=0) + 1

    entry = {
        "id": next_id,
        "scheduled_time": iso_time,
        "account": account,
        "text": text,
        "image_file": image,
        "status": "pending",
        "added_at": datetime.now(BERLIN).isoformat(),
    }
    queue.append(entry)

    QUEUE_PATH.write_text(
        json.dumps(queue, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Added post #{next_id} | {account} @ {iso_time}" + (f" with image {image}" if image else ""))


if __name__ == "__main__":
    main()
