"""
Auto-plug: put the CTA only under posts that actually earned attention.

THE PROBLEM IT SOLVES
  A fixed rule ("CTA on 1 of every 3 threads") sells under flops as often as under
  winners, and a feed with a link on every third post reads as a shop. Shawn's own
  measurement of a competitor: the root post got 15.9k views, its CTA reply got 780
  - and on a weak post, 638 -> 32. Selling under a post nobody read is pure noise.

  So the POST decides, not a quota. When a published thread crosses a real
  engagement bar, we reply once with the CTA. A thread that flops never gets one.

THRESHOLDS
  1,500 views OR 20 likes, whichever lands first. That is roughly 6x the current
  median (image posts ~238, text ~130), so only genuine outperformers qualify while
  still firing something in week one. Tune upward once threads have a track record -
  we have no baseline for the format on this account yet.

  MAX_PLUGS_PER_DAY = 1 per account is the real guard. If all three of a day's
  threads take off, we still sell exactly once.

NOTE ON PINNING
  The Threads API exposes no endpoint for pinning a reply, so the plug is published
  but not pinned. Shawn pins it by hand on the one post a day that earns it.
"""
import os
from datetime import datetime, timezone

import requests

from post_text import post_text

GRAPH = "https://graph.threads.net/v1.0"

# RECALIBRATED 2026-08-22. These were 1500 views / 20 likes, set when MAIN was
# medianing 685 views. Measured that day across the last 25 posts: median 119,
# max 293 - so ZERO posts could clear the old bar and all 119 attached CTAs were
# dead on arrival. A threshold set against historical reach silently disables the
# whole layer; it must track what the account actually does now.
#
# 250 / 6 puts the bar near the top decile of current posts. MAX_PLUGS_PER_DAY is
# the real guard anyway - the intent was always "the best post each day earns a
# CTA", not "a fixed view count".
#
# RE-MEASURE THIS whenever reach shifts materially, in either direction.
MIN_VIEWS = 250
MIN_LIKES = 6
MAX_PLUGS_PER_DAY = 1


def _token(account: str) -> str:
    key = f"{account}_TOKEN"
    token = os.environ.get(key)
    if not token:
        raise RuntimeError(f"Missing environment variable {key}")
    return token


def get_insights(account: str, post_id: str) -> dict:
    """Live {views, likes, replies} for one of our posts. {} if unavailable."""
    r = requests.get(
        f"{GRAPH}/{post_id}/insights",
        params={"metric": "views,likes,replies", "access_token": _token(account)},
        timeout=30,
    )
    r.raise_for_status()
    out = {}
    for item in r.json().get("data", []):
        # Threads returns total_value for lifetime metrics, values[] for time series.
        if "total_value" in item:
            out[item["name"]] = item["total_value"].get("value", 0)
        elif item.get("values"):
            out[item["name"]] = item["values"][0].get("value", 0)
    return out


def qualifies(stats: dict) -> bool:
    return (stats.get("views", 0) >= MIN_VIEWS) or (stats.get("likes", 0) >= MIN_LIKES)


def _root_id(entry: dict, target_key: str):
    """The id to hang the plug off: part 1 of the thread, or the single post."""
    result = (entry.get("results") or {}).get(target_key) or {}
    if result.get("status") != "posted":
        return None
    parts = result.get("thread_ids")
    if parts:
        return parts[0]
    return result.get("id")


def plugs_today(queue: list, account: str, now: datetime) -> int:
    today = now.date().isoformat()
    n = 0
    for entry in queue:
        plug = entry.get("auto_plug") or {}
        if plug.get("status") != "posted":
            continue
        if plug.get("account") != account:
            continue
        if str(plug.get("at", ""))[:10] == today:
            n += 1
    return n


def run(queue: list, now: datetime = None, log=print) -> bool:
    """Check every plug-eligible entry; publish CTAs that qualify.

    Returns True if the queue was modified. Never raises: a plug failing must not
    take down the publishing run that shares this tick.
    """
    now = now or datetime.now(timezone.utc)
    changed = False

    for entry in queue:
        plug = entry.get("auto_plug")
        if not plug or plug.get("status") != "pending":
            continue

        account = plug.get("account") or entry.get("account") or "MAIN"
        target_key = plug.get("target_key") or f"threads:{account}"

        root = _root_id(entry, target_key)
        if not root:
            continue  # not published yet (or that target failed) - check again later

        if plugs_today(queue, account, now) >= MAX_PLUGS_PER_DAY:
            continue  # today's single plug is already spent on a better post

        try:
            stats = get_insights(account, root)
        except Exception as e:
            log(f"auto-plug {entry.get('id','?')}: insights unavailable — {e}")
            continue

        if not qualifies(stats):
            continue

        try:
            plug_id = post_text(account, plug["text"], reply_to_id=root)
        except Exception as e:
            log(f"auto-plug {entry.get('id','?')}: publish failed — {e}")
            continue

        plug.update({
            "status": "posted",
            "id": plug_id,
            "account": account,
            "at": now.isoformat(),
            "stats_at_fire": stats,
        })
        changed = True
        log(f"auto-plug {entry.get('id','?')}: CTA posted under {root} "
            f"(views={stats.get('views')}, likes={stats.get('likes')}) — PIN IT MANUALLY")

    return changed
