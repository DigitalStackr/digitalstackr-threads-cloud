"""
Scheduler — runs every 5 min via GitHub Actions cron.
Reads queue.json, fires any posts whose scheduled_time falls within the current window,
updates status, writes log.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from post_text import post_text
from post_image import post_image

QUEUE_PATH = Path(__file__).parent / "queue.json"
LOG_PATH = Path(__file__).parent / "log.txt"


def log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"{stamp} | {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    log("=== Scheduler tick ===")

    if not QUEUE_PATH.exists():
        log("No queue.json found. Nothing to do.")
        return

    raw = QUEUE_PATH.read_text(encoding="utf-8").strip()
    if not raw or raw == "[]":
        log("Queue empty.")
        return

    queue = json.loads(raw)

    now = datetime.now(timezone.utc)
    # Larger catch-up window than local version since GitHub cron can drift up to 15 min
    window_start = now - timedelta(minutes=20)
    window_end = now + timedelta(seconds=30)

    fired_any = False

    for entry in queue:
        if entry.get("status") != "pending":
            continue

        try:
            sched = datetime.fromisoformat(entry["scheduled_time"]).astimezone(timezone.utc)
        except Exception as e:
            log(f"Post {entry.get('id', '?')}: unparseable time '{entry.get('scheduled_time')}' — {e}")
            continue

        if sched < window_start:
            log(f"Post {entry['id']}: scheduled {sched.isoformat()} is older than 20-min catch-up window — marking expired")
            entry["status"] = "expired"
            fired_any = True
            continue

        if sched <= window_end:
            account = entry["account"]
            text = entry["text"]
            image = entry.get("image_file")
            log(f"Post {entry['id']}: firing for {account} (scheduled {sched.isoformat()})")
            try:
                if image:
                    thread_id = post_image(account, text, image)
                else:
                    thread_id = post_text(account, text)
                entry["status"] = "posted"
                entry["thread_id"] = thread_id
                entry["posted_at"] = now.isoformat()
                log(f"Post {entry['id']}: OK -> thread_id={thread_id}")
            except Exception as e:
                entry["status"] = "failed"
                entry["error"] = str(e)
                log(f"Post {entry['id']}: FAILED — {e}")
            fired_any = True

    if fired_any:
        QUEUE_PATH.write_text(
            json.dumps(queue, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log("Queue updated.")
    else:
        log("Nothing due this tick.")


if __name__ == "__main__":
    main()
