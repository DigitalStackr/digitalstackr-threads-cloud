"""
Attach CTA replies (auto_plug blocks) to the pending Threads queue.

WHY THIS EXISTS
  auto_plug.py has worked correctly since it was written and has fired exactly
  ONCE. Not because the thresholds are wrong - because no queue entry carried an
  auto_plug block for it to act on. 110 pending Threads posts, zero CTAs. Every
  post between now and the end of the queue was going out with no next step.
  The mechanism was never broken; nothing was ever plugged into it.

WHAT FIRES, AND WHAT DOES NOT
  Attaching a plug does NOT mean a plug publishes. auto_plug still requires
  1,500 views or 20 likes, and still caps at MAX_PLUGS_PER_DAY = 1 per account.
  So attaching to all 110 is not 110 CTAs - it is "every post is eligible, the
  best one each day earns it." That is the intended design and the reason a flop
  never gets sold under.

CHOOSING THE OFFER  (the only real judgement call here)
  Measured 2026-08-20 by linking buyers across 536 Gumroad records:

      357  took a freebie, never paid
       35  paid without ever taking a freebie
       12  took a freebie FIRST, then paid   ->  3.3%,  $394.16

  So both paths earn. The freebie path produced ~20% of lifetime revenue with
  ZERO follow-up - nobody has ever emailed those 357 people. The direct path
  produced the rest.

  The split here is by READER INTENT, not by a quota:
    - proof/receipt/defiance post -> the reader just saw evidence and wants the
      system. Sell FDE.
    - origin/beginner post -> the reader is at zero. Asking $27 of someone who
      hasn't decided what to make is the mismatch that produces 357 non-buyers.
      Give the free thing, capture the email, sell later.

COPY RULES APPLIED
  House voice: lowercase, plain, understated. No engagement bait, no question
  endings, no ALL-CAPS, no hype emoji.

  NO DOLLAR FIGURES IN ANY PLUG. Deliberate. A plug is a reply and carries no
  screenshot of its own, so every figure in one is unbacked by definition. Fewer
  numbers also reads less like an ad directly under a post people just enjoyed.

  Shawn's example #4 ("twenty ready made digital products and an MRR license")
  is NOT used. Checked the live FDE description on the Gumroad API - it contains
  no such bundle and no resale licence. It would have been a false claim under a
  real post.

Run:  python attach_plugs.py [--apply]
Then: python validate_content.py queue.json
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validate_content import money_figures

HERE = Path(__file__).parent

# How far back a already-published post can still be given a CTA.
RECENT_HOURS = 48

FDE = "https://digitalstackr.gumroad.com/l/faceless-digital-empire"
IDEAS = "https://digitalstackr.gumroad.com/l/50-product-ideas"
ALGO = "https://digitalstackr.gumroad.com/l/threads-algo-boss-kit"

# Rotated so the same CTA never lands twice in a row on one account - these
# publish under the best post of the day, to a largely repeating audience.
PRODUCT_PLUGS = [
    "getting a lot of dms asking how this works.\n\n"
    "easier to put it in one place than answer it fifty times. what to sell, how "
    "to build it, how to set the store up so it keeps running when you're not "
    "there.\n\n" + FDE,

    "for everyone asking how — it's all written down.\n\n"
    "picking the product, building the thing, setting the store up, and what to "
    "actually post so people find it.\n\n" + FDE,

    "too many dms to answer one by one, so here's the honest version.\n\n"
    "none of it was luck. it's one repeatable setup, start to finish, and it's "
    "the same one i still use every week.\n\n" + FDE,

    "people keep asking what i'd do if i started from scratch tomorrow.\n\n"
    "this is that, written out. what to sell, how to make it, how to set it up "
    "so it can sell while you're asleep.\n\n" + FDE,

    "the system behind this isn't a secret, it's just long.\n\n"
    "so i wrote the whole thing down. no audience, no budget, no face — what to "
    "sell and how to get it in front of people.\n\n" + FDE,
]

FREEBIE_PLUGS = [
    "if you're stuck on step one, it's almost always picking the thing.\n\n"
    "here's fifty of them, free. work out what you'd actually make before you "
    "spend anything learning how.\n\n" + IDEAS,

    "getting views and no sales is an algo problem before it's a product "
    "problem.\n\n"
    "put the three prompts i used to fix mine into a free kit. just take it.\n\n"
    + ALGO,

    "if you're at zero right now, don't buy anything yet.\n\n"
    "start here instead. fifty product ideas, free. i lost weeks stuck on what "
    "to even make.\n\n" + IDEAS,
]

# "225 people bought", "32 buyers", "sold 70 copies" - a receipt without a $.
BUYER_COUNT_RE = re.compile(
    r"(?<!\w)\d[\d,]*\s+(?:people|buyers?|customers?|copies|sales?|orders?)(?!\w)"
    r"|(?<!\w)(?:sold|bought|paid)\s+(?:by\s+)?\d",
    re.I,
)

# Words that mark a post as spoken from the starting line rather than from proof.
BEGINNER_MARKERS = (
    "started", "starting", "start over", "from scratch", "eight months ago",
    "no audience", "no budget", "no experience", "zero followers", "at zero",
    "empty evenings", "nothing but a phone", "first sale", "first money",
    "before any of this", "used to think", "back then",
)


def offer_for(entry: dict) -> str:
    """product or freebie, decided by what the reader of THIS post needs next.

    HARD PROOF WINS over a beginner marker. Caught in the first dry run: id2102
    reads "$1,673.63 from 86 people ... eight months ago i had a phone" and the
    origin phrase sent it to a free idea list. Someone who has just been shown
    $1,673.63 is asking how it was done - handing them a beginner freebie there
    throws away the highest-intent moment the post creates. A receipt is a
    receipt no matter how humbly it is worded.
    """
    text = entry.get("text") or ""
    # Proof is not always a dollar sign. Second dry run caught three posts sent
    # to a freebie because the receipt was a HEADCOUNT: "225 people bought a PDF
    # from a teenager with no audience" and "32 people bought last week. i
    # started this year." Both are proof answering an objection - the strongest
    # sell moment there is - and both were classified as beginner content purely
    # because they contain "no audience" and "started".
    has_receipt = bool(money_figures(text)) or bool(BUYER_COUNT_RE.search(text))
    if has_receipt and entry.get("image_file"):
        return "product"
    low = text.lower()
    return "freebie" if any(m in low for m in BEGINNER_MARKERS) else "product"


def threads_accounts(entry: dict) -> list:
    targets = entry.get("targets") or [
        {"platform": "threads", "account": entry.get("account")}
    ]
    return [t["account"] for t in targets
            if t.get("platform", "threads") == "threads" and t.get("account")]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    apply = "--apply" in sys.argv
    path = HERE / "queue.json"
    queue = json.load(open(path, encoding="utf-8"))

    # Pending posts, PLUS anything published in the last RECENT_HOURS. A post that
    # went out this morning is still gaining views and can still cross the plug
    # threshold - auto_plug only needs a root id in results, which a posted entry
    # already has. Without this the first CTA cannot fire until tomorrow's queue
    # catches up, and today's live posts stay dead ends.
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)).isoformat()
    eligible = sorted(
        [e for e in queue
         if threads_accounts(e)
         and (e.get("status") == "pending"
              or (e.get("status") in ("posted", "partial")
                  and e.get("scheduled_time", "") >= cutoff))],
        key=lambda e: e["scheduled_time"],
    )
    pending = eligible

    rot = {}          # (account, kind) -> next variant index, keeps CTAs varied
    counts = {"product": 0, "freebie": 0, "skipped": 0}

    for entry in pending:
        if entry.get("auto_plug"):
            counts["skipped"] += 1
            continue

        account = threads_accounts(entry)[0]
        kind = offer_for(entry)
        pool = PRODUCT_PLUGS if kind == "product" else FREEBIE_PLUGS
        # TDS starts mid-pool so MAIN and TDS never carry the same CTA on the
        # same day. Their post text already differs by design; the reply should
        # not be the one identical thing across both feeds.
        start = 2 if account == "TDS" else 0
        i = rot.get((account, kind), start)
        rot[(account, kind)] = i + 1

        entry["auto_plug"] = {
            "status": "pending",
            "account": account,
            "target_key": f"threads:{account}",
            "text": pool[i % len(pool)],
        }
        counts[kind] += 1

    print(f"eligible threads entries: {len(pending)}  (pending + posted <{RECENT_HOURS}h)")
    print(f"  product CTA attached  : {counts['product']}")
    print(f"  freebie CTA attached  : {counts['freebie']}")
    print(f"  already had one       : {counts['skipped']}")

    print("\nfirst 10 assignments:")
    for e in pending[:10]:
        p = e.get("auto_plug") or {}
        head = (p.get("text") or "").split("\n")[0][:58]
        kind = "FREE" if any(u in p.get("text", "") for u in (IDEAS, ALGO)) else "PROD"
        print(f"  [{e['id']}] {p.get('account','?'):5s} {kind}  {head}")

    if not apply:
        print("\nDRY RUN — nothing written. re-run with --apply")
        return 0

    json.dump(queue, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nwritten to {path}")
    print("now run: python validate_content.py queue.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
