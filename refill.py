"""
Refills the Threads queue after it ran dry on 2026-08-14.

WHY THE GAP HAPPENED
  The previous batch ended Aug 14. The scheduler kept running (100/100 green) and
  found nothing to publish for 94 hours. Views halved because a 30-day rolling
  window filled up with zero-days, not because of the algorithm. Nothing warns
  when the queue empties - runway_check.py exists to close that hole.

STRUCTURE MIX - measured on this account, not assumed
  celebration          18.6k-27.5k, best follows-per-view of any post
  someone-paid          2,141 median
  happened-without-me   1,158 median  (best single 19.1k)
  identity/defiance       965 median  (best single 26.4k)
  quoted-objection        786 median  (best single 23.7k)
  plain receipt           349 median  <- deliberately absent

  Images lead with the 11 that have NOT appeared in the last 60 posts, so
  nothing looks recycled on the day we come back.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
TZ = timezone(timedelta(hours=2))

WEEKDAY = ["14:00", "16:30", "20:00", "22:00", "23:30", "01:30"]
WEEKEND = ["14:00", "16:30", "18:00", "20:00", "22:00", "23:00", "23:30", "01:30"]

# (structure, image, MAIN text, TDS text)
# Every figure checked against image_manifest.json.
POOL = [
    ("celebration", "Gumroad Payout Screenshots.PNG",
     "PAY DAY.\n\n$1638.53 deposited.\n\ni read the email four times before i accepted it had my name on it. \U0001f979",
     "an email that just opens with \"it's pay day\".\n\n$1638.53. i still have it saved."),

    ("someone-paid", "IMG_4395.PNG",
     "someone bought the $27 guide at 2:24pm.\ni was doing something completely unrelated. it went through anyway.",
     "$27, 2:24pm.\ni wasn't even looking at my phone. that's the part i can't get over."),

    ("happened-without-me", "Untitled design (17).png",
     "$201 from 19 people while i did nothing.\nno launch, no promo. just a file sitting somewhere people could find it.",
     "$201 from 19 people.\nquiet day. i'll take a quiet day that still pays."),

    ("identity", "IMG_3909.PNG",
     "they told me to get a job.\n\nthis is my lock screen. the $27 one is a file i wrote in february and never opened again.",
     "woke up to this.\ni was asleep for every single one of them."),

    ("quoted-objection", "Untitled design (13).png",
     "\"you're too young for anyone to take you seriously.\"\n\n$1,202.11 from 52 people who never asked how old i was.",
     "$1,202.11 from 52 people.\nnot one of them asked my age before paying."),

    ("celebration", "Untitled design (18).png",
     "i can finally say it.\n\n$1,673.63 from 86 people.\n\neight months ago i had a phone, no audience and no clue.",
     "$1,673.63 from 86 people.\nstarted with nothing but a phone and empty evenings."),

    ("someone-paid", "payout gumroad sales ss.png",
     "$1,109.77 in one payout window.\n\nfrom people i have never spoken to, for something i made once.",
     "$1,109.77 across one payout period.\ni didn't speak to a single one of them."),

    ("happened-without-me", "Untitled design(5).png",
     "$1,163.95 from 111 people.\ni was doing ordinary things for most of it. that is genuinely the whole pitch.",
     "111 people. $1,163.95.\nmy phone was in my pocket for most of that."),

    ("identity", "Untitled design (5).png",
     "no laptop in this photo. there isn't one.\n\nthe entire business runs off the screen i'm holding.",
     "this is the whole setup.\nno office, no team, no laptop. one screen."),

    ("quoted-objection", "gumroad more money dahsbaord.png",
     "\"nobody buys digital products anymore.\"\n\n70 people did. $1,183.32. i was asleep for a chunk of it.",
     "70 sales in a day.\ni was asleep for a good portion of them and still don't fully believe it."),

    # Items below reuse images that appeared Aug 8-14. Angles deliberately
    # rewritten from scratch - the validator caught the first draft recycling
    # last fortnight's wording almost verbatim.
    ("celebration", "IMG_4397.PNG",
     "104 people.\n\ni used to refresh this screen hoping for one.",
     "104 buyers this month.\nthere was a stretch where i'd have been happy with one."),

    ("someone-paid", "IMG_4274.PNG",
     "somebody handed me their entire launch and went to bed.\n\n$147, no meeting, no call, no questions.",
     "$147 and a message that said \"do whatever you think is best\".\nthat trust is heavier than the money."),

    ("happened-without-me", "gumroad notification screenshot.PNG",
     "i found out about this one at breakfast.\n\nit happened at 3:33am and the store just handled it.",
     "3:33am sale. found out over cereal.\nnobody warns you how strange that feels the first time."),

    ("identity", "3.9k gumroad ss.png",
     "225 people bought a PDF from a teenager with no audience.\n\nnot a genius. not connected. not lucky. just relentless about a boring thing. \U0001f62d\U0001f4b8",
     "225 strangers, one file, zero ads.\nthe only unusual thing about me is that i didn't quit in month two."),

    ("quoted-objection", "Untitled design (10).png",
     "\"this only works if you got in early.\"\n\n32 people bought last week. i started this year.",
     "\"you're too late for this.\"\n32 buyers say otherwise, and i started in february."),

    ("celebration", "Untitled design(4).png",
     "92 people.\n\nnone of them know my name, my face, or my voice. they just wanted the thing.",
     "$856.23 and not one person asked who i was.\nturns out they only care whether it works."),

    ("someone-paid", "IMG_3795.PNG",
     "someone paid for two weeks of my attention.\n\ni'm 19. i had to sit down for a second after that one.",
     "a stranger bought two weeks of my time.\nstill the single most surreal notification i've had."),

    ("happened-without-me", "IMG_3944.PNG",
     "i was queuing for coffee when this came through.\n\ndidn't check my phone for an hour. it had already happened.",
     "$181.30 while i was stood in a queue doing nothing.\nthat was the moment it clicked for me."),

    ("identity", "Untitled design(6).png",
     "everyone told me i needed a proper setup first.\n\n88 people bought from a file made on a phone.",
     "no desk. no camera. no editing software.\n88 people bought it anyway."),

    ("quoted-objection", "Untitled design (8).png",
     "\"you have to pay for reach now.\"\n\n24 people bought this week and i have never spent a penny on ads.",
     "\"organic is dead.\"\n24 buyers, zero ad spend, this week."),

    ("celebration", "Untitled design (11).png",
     "i can say it now.\n\n$739.50 from 65 people.\n\n65 strangers trusted a guide written by a teenager.",
     "$739.50 from 65 people.\ni've refreshed this screen about four times."),

    ("someone-paid", "gumroad sales notifications.PNG",
     "$27, an hour ago, from a file i wrote in february and haven't opened since.",
     "$27 again.\nsame guide. the one i almost didn't publish because it felt too obvious."),

    ("happened-without-me", "paypal notification ss from phn.png",
     "$1117.67 moved into paypal without me touching anything.\n\nfor something i wrote six months after learning it myself.",
     "$1117.67 landed in paypal.\ni wrote the thing one step ahead of the people buying it."),

    ("identity", "Untitled design (15).png",
     "they said it was a phase.\n\n662 orders later i'm still doing the same boring thing every single day.",
     "662 orders.\nsame boring routine every day. that's the secret, annoyingly."),
]


def build(start_day, days, start_id, now):
    out, eid, i = [], start_id, 0
    for d in range(days):
        day = start_day + timedelta(days=d)
        for hhmm in (WEEKEND if day.weekday() >= 5 else WEEKDAY):
            hh, mm = map(int, hhmm.split(":"))
            when = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if hh < 6:                      # 01:30 belongs to the next morning
                when += timedelta(days=1)
            if when <= now:                 # never schedule into the past
                continue
            structure, img, main, tds = POOL[i % len(POOL)]
            i += 1
            out.append({"id": eid, "scheduled_time": when.isoformat(), "status": "pending",
                        "image_file": img, "text": main,
                        "targets": [{"platform": "threads", "account": "MAIN"},
                                    {"platform": "x"}]})
            eid += 1
            out.append({"id": eid,
                        "scheduled_time": (when + timedelta(minutes=10)).isoformat(),
                        "status": "pending", "image_file": img, "text": tds,
                        "targets": [{"platform": "threads", "account": "TDS"}]})
            eid += 1
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = json.load(open(HERE / "queue.json", encoding="utf-8"))
    now = datetime.now(TZ)
    start_id = max(e["id"] for e in q) + 1
    batch = build(now.replace(hour=0, minute=0, second=0, microsecond=0), 3, start_id, now)
    print(f"generated {len(batch)} entries, ids {batch[0]['id']}-{batch[-1]['id']}")
    print(f"  first: {batch[0]['scheduled_time'][:16]}")
    print(f"  last : {batch[-1]['scheduled_time'][:16]}")
    print(f"  unique captions: {len({e['text'] for e in batch})}")
    json.dump(q + batch, open(HERE / "queue.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    json.dump(batch, open(HERE / "refill_batch.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
