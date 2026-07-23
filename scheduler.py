"""
Scheduler — runs every 5 min via GitHub Actions cron (or external cron-job.org trigger).

Reads queue.json, fires any posts whose scheduled_time falls within the current window,
updates status, writes log. Handles GitHub cron delays gracefully.

MULTI-PLATFORM (backward compatible):
  A queue entry may fan out to several destinations via a "targets" list, e.g.
    {
      "id": 500, "text": "shared caption", "image_file": "foo.png",
      "scheduled_time": "...", "status": "pending",
      "targets": [
        {"platform": "threads", "account": "MAIN"},
        {"platform": "threads", "account": "TDS", "text": "TDS-specific variant"},
        {"platform": "facebook"}
      ]
    }
  Per-target "text"/"image_file" override the entry-level ones (platform variants).

  LEGACY entries (no "targets", just {"account": "MAIN", ...}) are treated as a
  single Threads target — nothing about existing behavior changes.

  Each target fires INDEPENDENTLY. One platform failing never blocks the others.
  Per-target outcomes are recorded in entry["results"]; overall entry status
  becomes "posted" (all ok), "partial" (some ok), or "failed" (none ok).
  A "partial" entry retries only its NOT-yet-posted targets on the next tick
  (already-posted targets are never re-sent), until the catch-up window closes.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from post_text import post_text
from post_image import post_image
from post_facebook import post_facebook

QUEUE_PATH = Path(__file__).parent / "queue.json"
LOG_PATH = Path(__file__).parent / "log.txt"

# How far back in time we'll still fire a post that was scheduled.
CATCHUP_WINDOW_MIN = 90

# Max ENTRIES to fire per single tick — prevents spam-burst if we get behind.
# (One entry may fan out to several platforms; that still counts as one entry.)
MAX_POSTS_PER_TICK = 3

# Statuses that are still eligible to fire (partial => retry the failed targets).
FIREABLE_STATUSES = {"pending", "partial"}

REPO_SLUG = "DigitalStackr/digitalstackr-threads-cloud"


def log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"{stamp} | {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def raw_image_url(image_filename: str) -> str:
    """Public URL for a repo image (used by platforms that fetch images by URL)."""
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/main/images/{quote(image_filename)}"


def get_targets(entry: dict) -> list:
    """Return the list of targets for an entry. Legacy entries -> single Threads target."""
    targets = entry.get("targets")
    if targets:
        return targets
    return [{"platform": "threads", "account": entry.get("account", "MAIN")}]


def target_key(t: dict) -> str:
    platform = t.get("platform", "threads")
    if platform == "threads":
        return f"threads:{t.get('account', 'MAIN')}"
    return platform


def dispatch(entry: dict, target: dict) -> str:
    """Fire ONE target. Returns the platform's post id. Raises on failure."""
    platform = target.get("platform", "threads")
    text = target.get("text") if target.get("text") is not None else entry.get("text", "")
    image_file = target.get("image_file") or entry.get("image_file")

    if platform == "threads":
        account = target["account"]
        if image_file:
            return post_image(account, text, image_file)
        return post_text(account, text)

    if platform == "facebook":
        image_url = raw_image_url(image_file) if image_file else None
        return post_facebook(text, image_url)

    # x / tiktok land here until implemented — isolated as a failed target,
    # never crashes the tick or blocks the other platforms.
    raise ValueError(f"Platform not implemented yet: {platform}")


def fire_entry(entry: dict, now_iso: str) -> bool:
    """Fire all not-yet-posted targets of one entry. Returns True if any attempt was made."""
    targets = get_targets(entry)
    results = entry.get("results") or {}
    attempted = False

    for t in targets:
        key = target_key(t)
        if results.get(key, {}).get("status") == "posted":
            continue  # already delivered on a previous tick — never double-post
        attempted = True
        log(f"Post {entry['id']}: firing -> {key}")
        try:
            post_id = dispatch(entry, t)
            results[key] = {"status": "posted", "id": post_id, "at": now_iso}
            log(f"Post {entry['id']}: OK {key} -> {post_id}")
        except Exception as e:
            results[key] = {"status": "failed", "error": str(e)}
            log(f"Post {entry['id']}: FAILED {key} — {e}")

    entry["results"] = results

    statuses = [results.get(target_key(t), {}).get("status", "failed") for t in targets]
    if all(s == "posted" for s in statuses):
        entry["status"] = "posted"
    elif any(s == "posted" for s in statuses):
        entry["status"] = "partial"
    else:
        entry["status"] = "failed"
    entry["posted_at"] = now_iso

    # Preserve the legacy single-Threads field for readability.
    if len(targets) == 1 and targets[0].get("platform", "threads") == "threads":
        r = results.get(target_key(targets[0]), {})
        if r.get("status") == "posted":
            entry["thread_id"] = r["id"]

    return attempted


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
    now_iso = now.isoformat()
    window_start = now - timedelta(minutes=CATCHUP_WINDOW_MIN)
    window_end = now + timedelta(seconds=30)

    changed = False
    candidates = []
    for entry in queue:
        if entry.get("status") not in FIREABLE_STATUSES:
            continue
        try:
            sched = datetime.fromisoformat(entry["scheduled_time"]).astimezone(timezone.utc)
        except Exception as e:
            log(f"Post {entry.get('id', '?')}: unparseable time '{entry.get('scheduled_time')}' — {e}")
            continue

        if sched < window_start:
            log(f"Post {entry['id']}: scheduled {sched.isoformat()} older than "
                f"{CATCHUP_WINDOW_MIN}-min catch-up window — marking expired")
            entry["status"] = "expired"
            changed = True
            continue

        if sched <= window_end:
            candidates.append((sched, entry))

    candidates.sort(key=lambda x: x[0])  # oldest first

    fired_entries = 0
    for sched, entry in candidates:
        if fired_entries >= MAX_POSTS_PER_TICK:
            log(f"Post {entry['id']}: due but hit MAX_POSTS_PER_TICK cap — will fire next tick")
            break
        if fire_entry(entry, now_iso):
            fired_entries += 1
            changed = True

    if changed:
        QUEUE_PATH.write_text(
            json.dumps(queue, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log(f"Queue updated. Fired {fired_entries} entr(y/ies) this tick.")
    else:
        log("Nothing due this tick.")


if __name__ == "__main__":
    main()
