"""
Rewrites every PENDING post onto the structures that measured best on this account.

THE CORRECTION THIS IS BUILT ON
  Shawn pulled the true top 5 from the Threads app (includes posts he made by
  hand, which never appear in queue.json). The $382 figure - the one the July
  reset treated as the safe, small, believable number - took 18,600 views when it
  was framed as a milestone:

      "ITS FINALLY OFFICIAL!!!!! I can finally say it...
       I made $382 just this month in 7 days 🥹✨ Forever grateful."   18,600

      "$382 this month from 104 people. not life changing..."             274

  Same number, 68x apart. The problem was never the size of the figure; it was
  that "here is a number" is not a post. CELEBRATION is the missing structure -
  and on follows-per-view it beats every other post on the account.

RANKING USED (median views, MAIN, 30 days + Shawn's app data)
  1 celebration / milestone   18.6k-27.5k, best follows-per-view
  2 someone paid me           2,141 median
  3 happened without me       1,158 median  (best single: 19.1k)
  4 identity / defiance         965 median  (best single: 26.4k)
  5 quoted objection            786 median  (best single: 23.7k)
  x plain receipt               349 median  <- was 61% of output. Now capped.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

# Structures in rotation order. Each: (structure, image, MAIN text, TDS text)
# Every figure checked against image_manifest.json.
ROTATION = [
    ("celebration", "3.9k gumroad ss.png",
     "IT'S OFFICIAL.\n\n$3,937.55. 225 people.\n\ni started this on a phone with 49 followers and no idea what i was doing. still can't quite say it out loud. 🥹",
     "it's official.\n\n$3,937.55 from 225 people.\n\n49 followers when i started. i genuinely thought nothing would come of it."),

    ("someone-paid", "IMG_4274.PNG",
     "someone paid $147 for me to build the whole thing for them.\nthat's the part nobody expects.",
     "$147 to build someone else's store.\ni'm 19 and they handed me their launch anyway."),

    ("happened-without-me", "gumroad notification screenshot.PNG",
     "a sale came in at 3:33am.\nphone face down, dead asleep. it happened without me.",
     "3:33am. asleep.\nthe store doesn't know what time it is and that's the whole point."),

    ("identity", "Untitled design(4).png",
     "19 years old.\n$856.23 from 92 people who have never seen my face.\n\nnot a genius. not connected. not lucky. i just didn't stop.",
     "92 people. $856.23.\nnone of them know my name or what i look like. it never came up."),

    ("quoted-objection", "Untitled design (10).png",
     "\"you need ads for this.\"\n\n$640.80 from 32 people. i have genuinely never run one and wouldn't know how to start.",
     "someone told me this market was saturated.\n$640.80 from 32 people that same week."),

    ("celebration", "IMG_4397.PNG",
     "i can finally say it.\n\n$382 this month. 104 people.\n\nnot life changing money. but it's the first i've earned that didn't cost me an hour of my life. 🥹",
     "$382 this month. 104 people.\n\nsmall. but it's the first money i've made that kept coming while i did other things."),

    ("someone-paid", "IMG_3795.PNG",
     "someone booked two weeks of my time.\nthey trusted a 19 year old with their launch. still sitting with that.",
     "somebody paid for two weeks of my time.\ni'm 19. i keep waiting for them to ask for a refund."),

    ("happened-without-me", "IMG_3944.PNG",
     "$181.30 landed while i was walking home.\nit had already happened. i just found out afterwards.",
     "$181.30 turned up while i was out.\nfirst money i ever made that i didn't have to be present for."),

    ("identity", "Untitled design(6).png",
     "they told me to get a job.\n\n$735.29 from 88 people, off a file i wrote once.\n\nthe PDF is the job.",
     "$735.29 from 88 people.\nbuilt on a phone, in the gaps between other things."),

    ("quoted-objection", "IMG_4395.PNG",
     "\"nobody buys PDFs anymore.\"\n\n$27. this afternoon.",
     "someone bought the $27 guide this afternoon.\ni was doing something else entirely."),

    ("plain-receipt", "Untitled design (17).png",
     "$201 from 19 people.\nquiet day. i'll take a quiet day that still pays.",
     "$201 from 19 people.\nnot a big day. still a day that paid."),

    ("happened-without-me", "Untitled design (8).png",
     "$224.52 from 24 people while i was in a lecture.\ni checked my phone after and just sat there for a second.",
     "$224.52 from 24 people.\nphone was in my bag the whole time."),

    ("celebration", "Gumroad Payout Screenshots.PNG",
     "PAY DAY.\n\n$1638.53 deposited.\n\ni read the email four times before i believed it was addressed to me. 💸",
     "an email that opens with \"it's pay day\".\n\n$1638.53. i've still got it saved."),

    ("quoted-objection", "Untitled design (11).png",
     "\"you're too young for anyone to take seriously.\"\n\n$739.50 from 65 people who never asked how old i was.",
     "$739.50 from 65 people.\nnot one of them asked my age before paying."),

    ("someone-paid", "paypal notification ss from phn.png",
     "$1117.67 into paypal.\n\nfor a thing i wrote about six months after learning it myself. that's the whole trick.",
     "$1117.67 landed in paypal.\ni wrote the thing one step ahead of the people buying it."),

    ("identity", "IMG_3909.PNG",
     "woke up to this lock screen.\n\nno alarm, no commute, no boss. the $27 one is a guide i wrote once in february.",
     "lock screen this morning.\ni was asleep for every single one of them."),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = HERE / "queue.json"
    q = json.load(open(path, encoding="utf-8"))

    # ONLY entries that publish to Threads. The first version of this rewrote
    # every pending entry and silently destroyed 7 Telegram-only value posts by
    # replacing their text and retargeting them at Threads + X.
    def is_threads(e):
        return any(t.get("platform") == "threads" for t in (e.get("targets") or []))

    pending = [e for e in q if e.get("status") == "pending" and is_threads(e)]
    pending.sort(key=lambda e: e["scheduled_time"])
    skipped = sum(1 for e in q if e.get("status") == "pending" and not is_threads(e))
    print(f"pending Threads entries to rewrite: {len(pending)}  "
          f"(left alone: {skipped} non-Threads)")

    # MAIN and TDS sit 10 min apart, so they are adjacent once sorted - pair on
    # position. Keying on timestamp treats 14:00 and 14:10 as separate slots and
    # silently duplicates captions (learned this the hard way).
    counts, converted = {}, 0
    for pos, e in enumerate(pending):
        structure, img, main_text, tds_text = ROTATION[(pos // 2) % len(ROTATION)]
        acct = None
        for t in (e.get("targets") or []):
            if t.get("platform") == "threads":
                acct = t.get("account")
        e.pop("thread_parts", None)
        e.pop("auto_plug", None)
        e["image_file"] = img
        e["text"] = tds_text if acct == "TDS" else main_text
        e["targets"] = [{"platform": "threads", "account": acct or "MAIN"},
                        {"platform": "x"}]
        counts[structure] = counts.get(structure, 0) + 1
        converted += 1

    json.dump(q, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"rewrote {converted} entries\n")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    plain = counts.get("plain-receipt", 0)
    print(f"\nplain receipts: {plain}/{converted} = {plain/converted*100:.0f}% "
          f"(was 61% of all output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
