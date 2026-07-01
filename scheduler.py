"""
Scheduler — runs every 5 min via GitHub Actions cron (or external cron-job.org trigger).

Reads queue.json, fires any posts whose scheduled_time falls within the current window,
updates status, writes log. Handles GitHub cron delays gracefully.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from post_text import post_text
from post_image import post_image

QUEUE_PATH = Path(__file__).parent / "queue.json"
LOG_PATH = Path(__file__).parent / "log.txt"

# How far back in time we'll still fire a post that was scheduled.
# 90 min gives us cushion for GitHub cron delays (which can be up to 60+ min on free tier).
CATCHUP_WINDOW_MIN = 90

# Max posts to fire per single tick — prevents spam-burst if we get behind.
MAX_POSTS_PER_TICK = 3


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
    window_start = now - timedelta(minutes=CATCHUP_WINDOW_MIN)
    window_end = now + timedelta(seconds=30)

    # First pass: mark posts that are older than the catch-up window as expired.
    # Second pass: fire posts that are within window, up to MAX_POSTS_PER_TICK.
    fired_any = False

    # Sort candidates by scheduled_time so we fire oldest-first
    candidates = []
    for entry in queue:
        if entry.get("status") != "pending":
            continue
        try:
            sched = datetime.fromisoformat(entry["scheduled_time"]).astimezone(timezone.utc)
        except Exception as e:
            log(f"Post {entry.get('id', '?')}: unparseable time '{entry.get('scheduled_time')}' — {e}")
            continue

        if sched < window_start:
            log(f"Post {entry['id']}: scheduled {sched.isoformat()} is older than {CATCHUP_WINDOW_MIN}-min catch-up window — marking expired")
            entry["status"] = "expired"
            fired_any = True
            continue

        if sched <= window_end:
            candidates.append((sched, entry))

    # Sort by scheduled time, fire oldest first
    candidates.sort(key=lambda x: x[0])
    fired_count = 0

    for sched, entry in candidates:
        if fired_count >= MAX_POSTS_PER_TICK:
            log(f"Post {entry['id']}: due but hit MAX_POSTS_PER_TICK cap — will fire next tick")
            break

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
        fired_count += 1

    if fired_any:
        QUEUE_PATH.write_text(
            json.dumps(queue, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log(f"Queue updated. Fired {fired_count} post(s) this tick.")
    else:
        log("Nothing due this tick.")


if __name__ == "__main__":
    main()
