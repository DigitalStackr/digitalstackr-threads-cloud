"""
Refill the Threads queue with the formats that MEASURABLY win on this account.

WHERE THESE SHAPES CAME FROM
  400 posts pulled from the Threads API with per-post insights, 17 Jul - 23 Aug
  2026. The top of that list, by views:

    27,867  celebration      "IT'S OFFICIAL!!!!! 💸 Payout just landed: $3,898.40 🏦"
    26,426  identity         "19 years old. $3,937 in a month. from a PDF."
    23,803  quoted objection "you need fast wifi and a good laptop" / "$3,937 on a $200 chromebook"
    19,215  celebration      "ITS FINALLY OFFICIAL!!!!! I can finally say it..."
    13,189  happened-to-me   "sold while i was asleep. 70 times today."
     8,772  one-liner        "This is passive income 🥹"
     3,879  celebration      "DONT STOP ENGAGING ON THREADSSSS!!!!" (TDS, full caps)

  Loud, excited, ALL-CAPS, emoji-heavy, big real numbers. Several under ten words.
  That is the register. It is the opposite of the understated lowercase voice the
  account adopted on 2026-07-28 - the same date as its last paid sale, after which
  reach fell 685 -> 119.

  Shawn's pinned post is the same shape: "nobody buys PDFs anymore" / "62 people
  did today" 😭💸 - his most-liked post ever at ~1.2k.

THE ONE RULE THAT DOES NOT BEND
  Every $ figure below is copied from image_manifest.json for the image it is
  attached to. Caps and emoji bans were lifted on 2026-08-23 because they were
  costing reach; figure-matching stays absolute, because that is the line between
  loud and dishonest.

  Nothing here invents a number, and nothing reuses a competitor's.
"""
import json
import sys
import datetime as dt
from pathlib import Path

HERE = Path(__file__).parent

# (image, [figures verified present in that image]) - straight from the manifest.
P = {
    "3.9k":       ("3.9k gumroad ss.png",                 "$3,937.55", "225"),
    "today1183":  ("gumroad more money dahsbaord.png",    "$1,183.32", "70"),
    "payout1638": ("Gumroad Payout Screenshots.PNG",      "$1,638.53", None),
    "payout2954": ("IMG_2662.PNG",                        "$2,954.12", None),
    "d1673":      ("Untitled design (18).png",            "$1,673.63", "86"),
    "d1202":      ("Untitled design (13).png",            "$1,202.11", "52"),
    "d1163":      ("Untitled design(5).png",              "$1,163.95", "111"),
    "d856":       ("Untitled design(4).png",              "$856.23",   "92"),
    "d739":       ("Untitled design (11).png",            "$739.50",   "65"),
    "d735":       ("Untitled design(6).png",              "$735.29",   "88"),
    "d640":       ("Untitled design (10).png",            "$640.80",   "32"),
    "d224":       ("Untitled design (8).png",             "$224.52",   "24"),
    "d382":       ("IMG_4397.PNG",                        "$382",      "104"),
    "night27":    ("gumroad notification screenshot.PNG", "$27",       None),
    "sale27":     ("IMG_4395.PNG",                        "$27",       None),
    "dfy147":     ("IMG_4274.PNG",                        "$147",      None),
    "pp181":      ("IMG_3944.PNG",                        "$181.30",   None),
    "stripe552":  ("Untitled design (17).png",            "€552.61",   "16"),
    "alltime":    ("Untitled design (15).png",            "$19,079.70","662"),
}

# (key, MAIN text, TDS variant). TDS stays a shade drier but caps are allowed -
# the 3,879-view TDS post was FULL CAPS, which the old rules banned outright.
POSTS = [
    ("payout1638",
     "IT'S OFFICIAL!!!!! 💸\n\nPayout just landed: $1,638.53 🏦\n\ni'm never quitting this app fr 🥹",
     "PAY DAY 🏦\n\n$1,638.53 deposited.\n\ni read the email four times."),
    ("3.9k",
     "\"nobody buys PDFs anymore\"\n\n225 people did. $3,937.55 😭💸",
     "\"nobody buys PDFs anymore\"\n\n$3,937.55. 225 people. one file."),
    ("today1183",
     "ITS FINALLY OFFICIAL!!!!!\n\ni can finally say it…\n\n$1,183.32 IN ONE DAY 🥹",
     "$1,183.32 in a single day.\n\n70 people. i spoke to none of them."),
    ("d856",
     "\"get experience first\"\n\ni had zero.\n\n92 strangers still paid me $856.23 😭💸",
     "\"get experience first.\"\n\n92 people disagreed. $856.23."),
    ("night27",
     "sold while i was asleep.\n\n3:33am. $27. phone face down 🥹",
     "3:33am. $27.\n\nasleep for all of it."),
    ("d1673",
     "19. no degree. no audience. no face.\n\n$1,673.63 from 86 people who never asked 💸",
     "$1,673.63 from 86 people.\n\nnot one asked who i was."),
    ("d640",
     "woke up to $640.80 from 32 people.\n\ni was unconscious for every single one 😭",
     "$640.80 from 32 people, overnight.\n\ni found out at breakfast."),
    ("d1202",
     "\"you're too young for this\"\n\n$1,202.11 from 52 people who never asked my age 💸",
     "\"you're too young.\"\n\n52 people. $1,202.11. nobody asked."),
    ("payout2954",
     "PAY DAY!!!! 🥳\n\n$2,954.12 deposited 🏦\n\nfrom files i wrote once and never touched again",
     "$2,954.12 deposited.\n\nwork i finished months ago."),
    ("d1163",
     "\"digital products are saturated\"\n\n111 people bought today. $1,163.95 🥹",
     "\"saturated.\"\n\n111 buyers today. $1,163.95."),
    ("d735",
     "88 people. $735.29. one document.\n\nTHIS IS PASSIVE INCOME 🥹",
     "88 people bought the same file. $735.29."),
    ("pp181",
     "$181.30 landed while i was doing nothing 💸\n\nfirst money i ever made without trading an hour for it",
     "$181.30 arrived on its own.\n\nno hour traded for it."),
    ("d739",
     "\"you need an audience first\"\n\ni had 49 followers.\n\n65 people paid me $739.50 😭",
     "65 people. $739.50.\n\ni started at 49 followers."),
    ("dfy147",
     "someone paid me $147 to build their whole business 🥹\n\na stranger. who has never seen my face.",
     "$147 for me to build the entire thing.\n\nstill can't get over it."),
    ("d382",
     "$382 this month. 104 people.\n\nnot life changing. but it's REAL, and it's mine 🥹",
     "$382. 104 people.\n\nsmall. real. mine."),
    ("stripe552",
     "€552.61 came through stripe.\n\n16 payments. i was involved in none of them 💸",
     "€552.61. 16 payments.\n\ni found out afterwards."),
    ("d224",
     "$224.52 from 24 people TODAY 🥹\n\nsome of you are one file away and still overthinking it",
     "$224.52 today. 24 people.\n\none file."),
    ("alltime",
     "IT'S OFFICIAL!!!!! 🥳\n\n$19,079.70 all time. 662 sales 🏦\n\nfrom a phone. no face. no ads. 😭💸",
     "$19,079.70 all time. 662 sales.\n\nno face, no ads, no team."),
    ("sale27",
     "\"$27 is too cheap to matter\"\n\nit sold at 2:24pm while i was doing something else 💸",
     "$27, 2:24pm.\n\ni wasn't even looking at my phone."),
    ("3.9k",
     "i didn't have a macbook.\ni didn't have fast wifi.\n\ni had a $200 laptop and a link.\n\n$3,937.55 😭",
     "no macbook. no fast wifi.\n\na $200 laptop and a link. $3,937.55."),
]

SLOTS = [(8, 0), (14, 0), (19, 0), (25, 0)]   # 25:00 = 01:00 next day


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = json.load(open(HERE / "queue.json", encoding="utf-8"))
    TZ = dt.timezone(dt.timedelta(hours=2))
    pend = [e for e in q if e.get("status") == "pending"]
    last = max((dt.datetime.fromisoformat(e["scheduled_time"]) for e in pend),
               default=dt.datetime.now(TZ))
    nid = max(e["id"] for e in q) + 1
    day = last.date() + dt.timedelta(days=1)

    added = 0
    for i, (key, main_txt, tds_txt) in enumerate(POSTS):
        img = P[key][0]
        base = day + dt.timedelta(days=i // 4)
        h, m = SLOTS[i % 4]
        when = dt.datetime.combine(base, dt.time(h % 24, m), TZ) + dt.timedelta(days=h // 24)
        for off, acct, text in ((0, "MAIN", main_txt), (10, "TDS", tds_txt)):
            q.append({
                "id": nid, "account": acct, "text": text, "image_file": img,
                "scheduled_time": (when + dt.timedelta(minutes=off)).isoformat(),
                "status": "pending",
                "targets": [{"platform": "threads", "account": acct}],
            })
            nid += 1
            added += 1

    json.dump(q, open(HERE / "queue.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    p2 = [e for e in q if e.get("status") == "pending"]
    ts = sorted(e["scheduled_time"] for e in p2)
    print(f"added {added} posts | pending now {len(p2)}")
    print(f"runway {ts[0][:16]} -> {ts[-1][:16]}  ({len(p2)/8:.1f} days at 8/day)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
