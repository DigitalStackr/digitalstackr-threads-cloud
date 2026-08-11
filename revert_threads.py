"""
Reverts the pending long-form threads back to the single-post format.

WHY
  Measured on the live account, Aug 8-11 vs Jul 26-Aug 5:
      MAIN median views   685  ->  ~220
      views/day (both)  ~9,400 -> ~4,260
  Every format fell together - images as well as threads - which points at
  account-level throttling rather than a bad format. The most likely trigger is
  the thread engine itself: 7-11 posts published in ~21 seconds, 2-3x a day,
  took a steady 6-posts/day account to 20-30. Unproven, but the timing is exact
  and the cost of reverting is nothing.

WHAT THIS DOES
  Replaces every PENDING thread_parts entry with an image post built on the
  caption structures that actually performed on this account:

      26,423  identity + defiance + receipt
      13,019  disbelief + receipt
       9,061  faceless angle + receipt
       7,207  constraint/gear objection + receipt
       2,597  objection quote + receipt

  Already-posted threads are untouched - history stays honest.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

# (image, MAIN caption, TDS caption) - structures lifted from the top performers,
# figures checked against image_manifest.json.
REPLACEMENTS = [
    ("3.9k gumroad ss.png",
     "19 years old.\n$3,937.55 from 225 people. from a PDF.\n\nnot a genius. not connected. not lucky. i just didn't stop posting when it was embarrassing.",
     "225 people bought a PDF from a 19 year old.\n$3,937.55.\n\ni was not smarter than anyone. i just kept going past the embarrassing part."),

    ("IMG_4274.PNG",
     "someone paid $147 for me to build the whole thing for them.\nthat's the part nobody expects.",
     "$147 to build someone else's store.\ni'm 19 and they trusted me with their launch anyway."),

    ("Untitled design (10).png",
     "\"you need ads for this.\"\n$640.80 from 32 people. i have genuinely never run one.",
     "$640.80 from 32 people.\nzero ads. i wouldn't know how to start one."),

    ("IMG_3944.PNG",
     "they told me to get a job.\nthis is what the PDF paid out. $181.30 🤍",
     "$181.30 landed while i was out.\nfirst money i ever made that didn't cost me an hour."),

    ("Untitled design(4).png",
     "$856.23 from 92 people.\nnot one of them has seen my face or knows my name.",
     "92 people. $856.23.\nnone of them know what i look like. it never came up."),

    ("IMG_4395.PNG",
     "\"nobody buys PDFs anymore.\"\n$27. this afternoon.",
     "someone bought the $27 guide this afternoon.\ni was doing something else entirely."),

    ("Untitled design(6).png",
     "i didn't have a macbook.\ni didn't have fast wifi.\ni had a phone and a link.\n\n$735.29 from 88 people. the gear is a myth.",
     "$735.29 from 88 people.\nbuilt on a phone, in gaps between other things."),

    ("gumroad notification screenshot.PNG",
     "a sale came in at 3:33am.\nphone face down, dead asleep. it happened without me.",
     "3:33am. asleep.\nthe store doesn't know what time it is and that's the whole point."),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = HERE / "queue.json"
    q = json.load(open(path, encoding="utf-8"))

    pending_threads = [e for e in q
                       if e.get("status") == "pending" and e.get("thread_parts")]
    pending_threads.sort(key=lambda e: e["scheduled_time"])
    print(f"pending thread entries to convert: {len(pending_threads)}")

    # MAIN and TDS are the same slot 10 minutes apart, so they are ADJACENT once
    # sorted by time - pair on position, not on timestamp. Keying by timestamp
    # treated 14:00 and 14:10 as two slots, wrapped the cycle, and produced eight
    # duplicate captions.
    if len(pending_threads) % 2:
        print("WARNING: odd number of thread entries - pairs may be misaligned")
    pairs = (len(pending_threads) + 1) // 2
    if pairs > len(REPLACEMENTS):
        print(f"ERROR: {pairs} slots to fill but only {len(REPLACEMENTS)} "
              f"replacements written - would repeat captions. Aborting.")
        return 1

    converted = 0
    for pos, e in enumerate(pending_threads):
        img, main_text, tds_text = REPLACEMENTS[pos // 2]
        acct = None
        for t in (e.get("targets") or []):
            if t.get("platform") == "threads":
                acct = t.get("account")
        e.pop("thread_parts", None)
        e.pop("auto_plug", None)          # nothing to plug on a single post
        e["image_file"] = img
        e["text"] = tds_text if acct == "TDS" else main_text
        e["targets"] = [{"platform": "threads", "account": acct or "MAIN"},
                        {"platform": "x"}]
        converted += 1

    json.dump(q, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"converted {converted} entries to single image posts")
    print(f"remaining thread entries anywhere in queue: "
          f"{sum(1 for e in q if e.get('thread_parts'))} (all already posted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
