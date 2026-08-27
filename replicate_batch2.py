"""
Second replication batch, built on the 13 screenshots that were unlocked
2026-08-26. Extends runway AND fixes image monotony in one pass.

WHY THIS EXISTS
  The queue was leaning on the same handful of screenshots - '3.9k gumroad ss.png'
  four times in 30 posts - because only 32 images were usable and 13 more sat in
  `unverified_do_not_use`. Nobody had ever opened them, so the rule correctly
  blocked them. They are opened and recorded now, so rotation is 45 wide.

  Same register as batch one: loud, ALL-CAPS, emoji, real figures. That is what
  the 400-post pull says wins.

TWO TRAPS IN THIS BATCH
  1. 'gumrd dashbrd ss 856.png' shows $856.23 / 92 - the SAME figures as
     'Untitled design(4).png', which batch one already uses. Different crop of the
     same day. Both are legitimate but they must never run in the same week or the
     feed reads as one screenshot recycled.
  2. 'gum iphone dashabord w apps.png' carries FOUR figures. A caption may quote
     only one, and must label its period. The YEAR figure ($41,639) historically
     flopped at 60-90 views, so this quotes the WEEK.
"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

BATCH = [
    ("gumroad dashbaord ss 2k.png",
     "ITS OFFICIAL!!!!! 🥳\n\n$2,013.39 THIS MONTH 🏦\n\n81 people. one file. 😭💸"),
    ("paypal notification ss 1.3k.png",
     "PAY DAY 🏦\n\n$1,380.13 just landed.\n\nfrom something i wrote once 🥹"),
    ("dashbaord ss 964tdy.png",
     "$964.80 TODAY. 64 people.\n\ni keep checking to make sure it's real 😭💸"),
    ("612 a day gumroad dahsbaord ss.png",
     "$612 in a single day.\n26 people.\n\nnobody asked who i was 🥹"),
    # NOT the "get experience first" post - that already published 2026-08-25 with
    # "65 strangers", and re-running it with 66 is one digit changed, which is a
    # near-duplicate rather than a new post. Different angle, same verified figures.
    ("gum dashbrd ss 1kmon.png",
     "$1,109.77 THIS MONTH 🥳\n\n66 people.\n\ni was asleep for most of it 😭💸"),
    ("gumroad dahsbaord ss 556.png",
     "$556.26 from 32 people today 🥹\n\none document. that's the whole business."),
    ("digistackr sales proof.png",
     "$460.80. 18 people. today.\n\nnot life changing. but it's REAL 🥹"),
    ("sales proof.png",
     "37 people bought today. $453.92 💸\n\ni have never met a single one of them."),
    ("125 tdy gumroad dahsbaord.png",
     "$125 today from 24 people.\n\nsmall numbers still land while you sleep 🥹"),
    ("gumroad 112day.png",
     "$112.70. 17 people.\n\nEVERYONE starts here. i did 😭💸"),
    ("gum iphone dashabord w apps.png",
     "$1,963.86 THIS WEEK 🥳\n\nthreads. a doc. gumroad.\nthat is the entire stack 💸"),
    # Same trap: "$856.23 from 92 people / not one of them has seen my face"
    # already published on 'Untitled design(4).png'. Different structure here.
    ("gumrd dashbrd ss 856.png",
     "92 SALES IN ONE DAY 🥳\n\n$856.23 💸\n\ni still don't fully believe it 🥹"),
]

SLOTS = [8, 13, 16, 19, 22, 25]   # 25:00 == 01:00 next day


def accts(e):
    a = {t.get("account") for t in (e.get("targets") or [])
         if t.get("platform", "threads") == "threads" and t.get("account")}
    return a or ({e["account"]} if e.get("account") else set())


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = json.load(open(HERE / "queue.json", encoding="utf-8"))
    manifest = json.load(open(HERE / "image_manifest.json", encoding="utf-8"))["verified"]

    for img, _ in BATCH:
        if img not in manifest:
            raise SystemExit(f"UNVERIFIED IMAGE: {img}")
        if manifest[img].get("tier") == "blocked":
            raise SystemExit(f"BLOCKED IMAGE: {img}")

    # FIX: batch one said "65 strangers still paid me $1,109.77" on
    # 'payout gumroad sales ss.png'. The original winning post said 66, and the
    # screenshot that actually shows a count says 66. It was "corrected" to 65 to
    # match the Gumroad API - but the rule is that the caption must match the
    # SCREENSHOT, not the API, and that edit created the exact mismatch the rule
    # exists to prevent. Those entries are dropped; this batch re-runs the post
    # correctly on the image that shows the 66.
    dropped = 0
    for e in q:
        if e.get("status") == "pending" and "65 strangers" in (e.get("text") or ""):
            e["status"] = "held"
            e["held_reason"] = ("caption said 65 but the attached screenshot shows no "
                                "count; re-issued on 'gum dashbrd ss 1kmon.png' which "
                                "shows 66")
            dropped += 1

    TZ = dt.timezone(dt.timedelta(hours=2))
    now = dt.datetime.now(TZ)
    pend = [e for e in q if e.get("status") == "pending" and accts(e)]
    last = max((dt.datetime.fromisoformat(e["scheduled_time"]) for e in pend), default=now)

    nid = max(e["id"] for e in q) + 1
    added = 0
    for i, (img, text) in enumerate(BATCH):
        base = last.date() + dt.timedelta(days=1 + i // 6)
        h = SLOTS[i % 6]
        when = dt.datetime.combine(base, dt.time(h % 24, 0), TZ) + dt.timedelta(days=h // 24)
        for off, acct in ((0, "MAIN"), (10, "TDS")):
            q.append({
                "id": nid, "account": acct, "text": text, "image_file": img,
                "scheduled_time": (when + dt.timedelta(minutes=off)).isoformat(),
                "status": "pending",
                "targets": [{"platform": "threads", "account": acct}],
            })
            nid += 1
            added += 1

    json.dump(q, open(HERE / "queue.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    p = [e for e in q if e.get("status") == "pending"]
    ts = sorted(e["scheduled_time"] for e in p)
    print(f"held (65/66 mismatch): {dropped}")
    print(f"added: {added}")
    print(f"pending: {len(p)}   runway {ts[0][:16]} -> {ts[-1][:16]}  ({len(p)/12:.1f} days)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
