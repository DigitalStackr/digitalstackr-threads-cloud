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
from post_instagram import post_instagram
from post_tiktok import post_tiktok
from post_telegram import post_telegram

QUEUE_PATH = Path(__file__).parent / "queue.json"
# Local media dirs on the runner (TikTok uploads bytes rather than fetching a URL).
REELS_DIR = Path(__file__).parent / "reels"
# NOTE: logging goes to STDOUT only (captured by the GitHub Actions run log).
# We deliberately no longer commit a log.txt file — two runs both appending to the
# end of log.txt produced a *deterministic* `git rebase` conflict at EOF, which
# exhausted the push-back retries and failed the whole run (=> failure emails, and
# the queue update not being saved => double-post risk on the next tick). Dropping
# log.txt from git removes that conflict source entirely. LOG_PATH is kept only so
# the local test harness can still point logging somewhere harmless.
LOG_PATH = Path(__file__).parent / "log.txt"

# How far back in time we'll still fire a post that was scheduled.
CATCHUP_WINDOW_MIN = 90

# Max ENTRIES to fire per single tick — prevents spam-burst if we get behind.
# (One entry may fan out to several platforms; that still counts as one entry.)
MAX_POSTS_PER_TICK = 3

# Self-healing: how many times we'll auto-reschedule a post that failed to send or
# missed its window before we give up on it. Each retry pushes it forward by
# RETRY_DELAY_MIN minutes so a transient outage (token blip, Threads 5xx, missed
# cron) recovers on its own instead of the post being silently dropped/expired.
MAX_RETRIES = 5
RETRY_DELAY_MIN = 20

# Statuses that are still eligible to fire (partial => retry the failed targets).
FIREABLE_STATUSES = {"pending", "partial"}

REPO_SLUG = "DigitalStackr/digitalstackr-threads-cloud"


def log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"{stamp} | {msg}", flush=True)


def reschedule(entry: dict, now: datetime, reason: str) -> None:
    """Self-heal: push a failed/overdue entry forward so it retries later instead of
    being dropped. Only moves scheduled_time — already-'posted' targets are recorded
    in entry['results'] and are skipped by fire_entry, so this never double-posts."""
    entry["attempts"] = entry.get("attempts", 0) + 1
    new_time = now + timedelta(minutes=RETRY_DELAY_MIN)
    entry["scheduled_time"] = new_time.astimezone(timezone.utc).isoformat()
    log(f"Post {entry.get('id', '?')}: {reason} — auto-rescheduled to "
        f"{entry['scheduled_time']} (attempt {entry['attempts']}/{MAX_RETRIES})")


def raw_image_url(image_filename: str) -> str:
    """Public URL for a repo image (used by platforms that fetch images by URL)."""
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/main/images/{quote(image_filename)}"


def raw_video_url(video_filename: str) -> str:
    """Public URL for a repo video. Videos live in reels/ (Shawn drops CapCut/Remotion
    exports there); images stay in images/. Used by IG Reels + FB Reels."""
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/main/reels/{quote(video_filename)}"


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
    video_file = target.get("video_file") or entry.get("video_file")
    carousel = target.get("carousel") or entry.get("carousel")

    if platform == "threads":
        account = target["account"]
        if image_file:
            return post_image(account, text, image_file)
        return post_text(account, text)

    if platform == "facebook":
        image_url = raw_image_url(image_file) if image_file else None
        return post_facebook(text, image_url)

    if platform == "instagram":
        # BRAND POLICY: Instagram is REELS ONLY (decided 2026-07-27).
        # Two reasons this is enforced in code rather than left to convention:
        #   1. Shawn's explicit call — IG gets video, screenshots stay on Threads/FB.
        #   2. It's physically true anyway: every proof screenshot in images/ is a
        #      wide desktop crop (measured 1.91-3.12 aspect) and IG's feed only
        #      accepts 0.80-1.91, so images would be rejected by Meta regardless.
        # Failing loudly here beats a confusing 36003 from the API mid-schedule.
        if not video_file:
            raise ValueError(
                "Instagram is Reels-only: target needs video_file (an .mp4 in reels/). "
                "Images/carousels are not posted to Instagram."
            )
        return post_instagram(text, video_url=raw_video_url(video_file))

    if platform == "telegram":
        # Telegram fetches the image server-side from a public URL, same as FB/IG.
        # Text-only is fine here (unlike Instagram) — the channel is a feed, not a grid.
        image_url = raw_image_url(image_file) if image_file else None
        return post_telegram(text, image_url)

    if platform == "tiktok":
        # TikTok uploads BYTES (FILE_UPLOAD) rather than fetching a URL like Meta,
        # because PULL_FROM_URL needs a verified domain and we serve from
        # raw.githubusercontent.com. The repo is checked out on the runner, so the
        # file is local. Carousels stay unsupported until a domain is verified.
        if carousel:
            raise ValueError(
                "TikTok carousels need PULL_FROM_URL from a TikTok-verified domain "
                "(GitHub raw is not verifiable) — not enabled yet."
            )
        if not video_file:
            raise ValueError("TikTok target needs a video_file (an .mp4 in reels/)")
        return post_tiktok(text, str(REELS_DIR / video_file),
                           privacy_level=target.get("privacy_level"))

    # x lands here until implemented — isolated as a failed target,
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
            # Missed its catch-up window (cron gap / outage). Instead of silently
            # dropping it, self-heal: reschedule forward and retry — up to MAX_RETRIES.
            if entry.get("attempts", 0) < MAX_RETRIES:
                reschedule(entry, now, f"missed {CATCHUP_WINDOW_MIN}-min catch-up window")
            else:
                log(f"Post {entry['id']}: exhausted {MAX_RETRIES} retries — marking expired")
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
            # Self-heal: if every target failed this tick, don't leave it dead —
            # push it forward and make it fireable again (bounded by MAX_RETRIES).
            # 'partial' entries are left as-is: they stay FIREABLE and retry only
            # their not-yet-posted targets on the very next tick (faster than a
            # 20-min bump), and the window-expiry branch above will reschedule
            # them forward if they ever fall out of the catch-up window.
            if entry["status"] == "failed" and entry.get("attempts", 0) < MAX_RETRIES:
                reschedule(entry, now, "all targets failed this tick")
                entry["status"] = "pending"

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
