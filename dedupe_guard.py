"""
Last line of defence against double-posting to Threads.

THE BUG THIS FIXES (confirmed live 2026-08-19)
  9 duplicate posts across MAIN and TDS, published 58-153 seconds apart:

      "$1117.67 from gumroad into paypal..."     72s apart
      "10 THINGS I COULDN'T AFFORD AT 18."      153s apart
      "$27 again. same guide..."                  61s apart

  Cause: GitHub's cron and cron-job.org fire about a minute apart. Run A reads
  queue.json, sees status=pending, and publishes. Run B starts before A has
  finished its rebase-and-push cycle (which takes 60-90s), reads the SAME
  pending entry, and publishes it again. The `concurrency:` block does not
  reliably serialise the two, and merge_queue.py only protects the RECORD -
  by the time it runs, both posts are already live.

  Every previous guard lived in our own state, and our own state is exactly
  what is stale during the race. So this one asks Threads instead: has this
  text already gone out? The platform cannot be stale about its own posts.

COST
  One extra GET per Threads publish. Negligible next to the publish itself.

FAILURE POLICY
  If the check cannot run (network, token, rate limit) it returns None and
  publishing proceeds. A missed duplicate is bad; refusing to post at all
  because a lookup failed is worse.
"""
import os
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

GRAPH = "https://graph.threads.net/v1.0"

# Wide enough to cover the observed race (max seen: 153s) plus the catch-up
# window a self-healed retry can sit in, without reaching back so far that a
# deliberate re-run of an old caption is blocked.
LOOKBACK_MINUTES = 45


def _norm(text):
    """Compare on normalised text: platforms round-trip whitespace and unicode
    inconsistently, and an exact == would miss a duplicate over a stray space."""
    t = unicodedata.normalize("NFKC", (text or "")).strip().lower()
    return " ".join(t.split())


def already_posted(account, text, lookback_minutes=LOOKBACK_MINUTES):
    """Return the existing post id if this exact text is already live, else None.

    Returns None on any error - see FAILURE POLICY above.
    """
    token = os.environ.get(f"{account}_TOKEN")
    if not token or not (text or "").strip():
        return None
    try:
        r = requests.get(
            f"{GRAPH}/me/threads",
            params={"fields": "id,text,timestamp", "limit": 25, "access_token": token},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as e:
        print(f"dedupe: lookup failed for {account} ({e}) — allowing publish", flush=True)
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    want = _norm(text)
    for post in data:
        try:
            ts = datetime.fromisoformat(post["timestamp"].replace("+0000", "+00:00"))
        except Exception:
            continue
        if ts < cutoff:
            continue
        if _norm(post.get("text")) == want:
            return post.get("id")
    return None
