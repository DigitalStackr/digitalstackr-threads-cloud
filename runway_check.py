"""
Warns before the queue runs dry, and if publishing goes silent.

WHY THIS EXISTS
  On 2026-08-14 the queue emptied. The scheduler kept running perfectly - 100/100
  green - and published nothing for 94 hours across both accounts. Views halved
  because a 30-day rolling window filled with zero-days. Nothing anywhere said
  "you are out of content", so four days passed before anyone noticed.

  A green pipeline that is publishing nothing looks identical to a healthy one
  from the outside. This is the check that tells them apart.

Runs as a step in the normal scheduler tick, continue-on-error, so a Telegram
hiccup can never take down publishing.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

QUEUE = Path(__file__).parent / "queue.json"

RUNWAY_WARN_HOURS = 48     # shout when under two days of Threads content remain
SILENCE_ALERT_HOURS = 10   # shout if nothing has published in this long.
# Was 8, set when the grid ran 6 slots/day. The grid is now 4/day (08:00, 14:00,
# 19:00, 01:00 Berlin), so the legitimate overnight gap is 19:10 -> 01:00 and
# 01:10 -> 08:00, i.e. ~7h. At 8h this fired most nights on a perfectly healthy
# queue, and an alert that cries wolf nightly is one nobody reads - which is the
# same way the Aug 14 outage went unnoticed for 94 hours.
# Re-derive this if the slot grid changes again: it must exceed the largest
# INTENDED gap, with margin.

# GAP DETECTION - added 2026-08-23.
# RUNWAY_WARN_HOURS only looks at the LAST scheduled post, so a queue holding 74
# entries stretching to Aug 28 reports as perfectly healthy even with a 36-hour
# hole in the middle of it. That is exactly what happened on Aug 22: three posts
# went out all day, every scheduler run was green, nothing warned.
#
# Total runway and continuity are different properties. This checks continuity.
NEXT_POST_ALERT_HOURS = 12   # nothing scheduled within this many hours = page me
MAX_GAP_HOURS = 18           # a hole this big inside the queue = page me
GAP_LOOKAHEAD_HOURS = 96     # how far forward to inspect for holes


def threads_pending(queue, now):
    out = []
    for e in queue:
        if e.get("status") != "pending":
            continue
        if not any(t.get("platform") == "threads" for t in (e.get("targets") or [])):
            continue
        try:
            when = datetime.fromisoformat(e["scheduled_time"])
        except Exception:
            continue
        if when >= now:
            out.append(when)
    return sorted(out)


def last_threads_post(queue):
    stamps = []
    for e in queue:
        if not e.get("posted_at"):
            continue
        if not any(t.get("platform") == "threads" for t in (e.get("targets") or [])):
            continue
        try:
            stamps.append(datetime.fromisoformat(e["posted_at"].replace("Z", "+00:00")))
        except Exception:
            pass
    return max(stamps) if stamps else None


def due_now(now):
    """Throttle WITHOUT a state file.

    Each Actions run is a fresh checkout, so a local state file would not survive
    between runs and the alert would fire every 5 minutes. Committing the state
    instead would recreate the log.txt failure class - two concurrent runs both
    rewriting the same tracked file, conflicting on every rebase.

    So: alert only in the first tick of 08:00 and 20:00 UTC. At most twice a day,
    no state, no new committed file, nothing to conflict on."""
    return now.hour in (8, 20) and now.minute < 5


def alert(text):
    """Send an internal alert to the OWNER privately. Never to the channel.

    THIS PUBLISHED TO THE PUBLIC CHANNEL. TELEGRAM_OWNER was set to the handle
    "@digitalstackr" - which is the CHANNEL, not a person - so every runway
    warning went out as a post to real subscribers. They read internal plumbing
    messages saying the queue was empty.

    The guard below is the actual fix, not just the secret change: an operational
    alert must be structurally incapable of reaching an audience.

    A numeric chat id is REQUIRED, and that is not an arbitrary restriction -
    Telegram bots cannot message a user by @username at all, only by numeric id.
    So anything starting with "@" is by definition a channel or a group, i.e.
    exactly the thing we must not post to. Get the numeric id by messaging
    @userinfobot on Telegram, then set TELEGRAM_OWNER to it.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    owner = (os.environ.get("TELEGRAM_OWNER") or "").strip()
    channel = (os.environ.get("TELEGRAM_CHANNEL") or "").strip()

    if not (token and owner):
        print("runway: telegram not configured — would have alerted", flush=True)
        return False

    unsafe = None
    if owner.startswith("@"):
        unsafe = (f"TELEGRAM_OWNER is {owner!r} — a public handle. Internal alerts "
                  f"must go to a NUMERIC private chat id.")
    elif channel and owner.lstrip("-") == channel.lstrip("-").lstrip("@"):
        unsafe = "TELEGRAM_OWNER is the same target as TELEGRAM_CHANNEL."
    if unsafe:
        print(f"runway: REFUSING to send - {unsafe}", flush=True)
        print(f"        Alert content (logged, not published): {text!r}", flush=True)
        return False

    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": owner, "text": text}, timeout=20)
        return True
    except Exception as e:
        print(f"runway: telegram send failed ({e})", flush=True)
        return False


def main() -> int:
    if not QUEUE.exists():
        print("runway: no queue.json", flush=True)
        return 0
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)

    pending = threads_pending(queue, now)
    hours_left = (pending[-1] - now).total_seconds() / 3600 if pending else 0.0
    last = last_threads_post(queue)
    silent = (now - last).total_seconds() / 3600 if last else 999

    print(f"runway: {len(pending)} Threads posts queued | "
          f"{hours_left:.0f}h of content left | "
          f"{silent:.0f}h since last publish", flush=True)

    problems = []

    # --- continuity, not just total runway ---
    if pending:
        to_next = (pending[0] - now).total_seconds() / 3600
        if to_next > NEXT_POST_ALERT_HOURS:
            problems.append(
                f"NOTHING SCHEDULED FOR {to_next:.0f}h. Next post is "
                f"{pending[0].isoformat()[:16]}. The queue is not empty, but there "
                f"is a hole at the front of it.")
        horizon = now + timedelta(hours=GAP_LOOKAHEAD_HOURS)
        window = [p for p in pending if p <= horizon]
        for a, b in zip(window, window[1:]):
            gap = (b - a).total_seconds() / 3600
            if gap > MAX_GAP_HOURS:
                problems.append(
                    f"{gap:.0f}h GAP inside the queue: {a.isoformat()[:16]} -> "
                    f"{b.isoformat()[:16]}. Total runway looks fine; continuity "
                    f"does not.")
                break

    if hours_left < RUNWAY_WARN_HOURS:
        problems.append(f"Content runway low: {len(pending)} Threads posts left, "
                        f"about {hours_left:.0f}h. Refill before it empties.")
    if silent > SILENCE_ALERT_HOURS:
        problems.append(f"Nothing has published in {silent:.0f}h. The scheduler can be "
                        f"green while the queue is empty — that is what happened on Aug 14.")

    if not problems:
        print("  healthy", flush=True)
        return 0
    for p in problems:
        print(f"  PROBLEM: {p}", flush=True)
    if due_now(now):
        # One message covering everything, rather than one per problem.
        if alert("DigitalStackr — automation check\n\n" + "\n\n".join(problems)):
            print("  alert SENT", flush=True)
    else:
        print("  (outside alert window 08:00/20:00 UTC — logged only)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
