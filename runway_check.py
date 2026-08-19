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
SILENCE_ALERT_HOURS = 8    # shout if nothing has published in this long


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
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    owner = os.environ.get("TELEGRAM_OWNER")
    if not (token and owner):
        print("runway: telegram not configured — would have alerted", flush=True)
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
