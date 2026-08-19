"""
Gives X its own long-form content instead of recycled Threads captions.

WHY
  All 55 pending X targets were inheriting the Threads caption - roughly 100
  characters plus a screenshot. That is the Threads format. X rewards the
  opposite: a long, numbered, useful breakdown. Shawn's own X posts confirm it -
  his single best performer was a long one at 31 views against single digits
  for the short ones.

WHAT IS DELIBERATELY NOT COPIED FROM THE COMPETITORS HE SENT
  Two of the three examples are comment-gated ("comment DPC and i'll send the
  guide"). That is banned content on this account, it needs reply automation we
  have not built, and it needs an audience that comments - X has 3 followers.
  The third example is an outright fake ($3,024,127 PayPal balance,
  "100% GUARANTEED"). None of that is copied.

  What IS copied is the shape: a claim, a numbered breakdown, concrete steps,
  no fluff.

LINKS AND COST
  Each post ends with the product URL. post_x.py strips it out of the body and
  publishes it as a threaded reply, because a link in the body bills at $0.20
  against $0.015. So the link still reaches readers, in the first comment, at
  a fourteenth of the cost. Nothing extra to build.

EXPECTATIONS
  X has produced zero orders across all 522 records. This is a test of format
  on an account with 3 followers, not a growth plan. Judge it on whether any
  post clears ~200 views, not on sales.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
LINK = "https://digitalstackr.gumroad.com/l/faceless-digital-empire"

POSTS = [
    "i sell digital products from my phone. no ads, no face, no team.\n\n"
    "here is the entire setup, in order:\n\n"
    "1. pick a problem you have personally solved. not one you researched.\n"
    "2. write the steps you took, in a plain doc. no design yet.\n"
    "3. put it in canva. one hour, not one week.\n"
    "4. upload to gumroad. they take payment and send the file.\n"
    "5. post about the problem daily. not the product.\n\n"
    "that is it. i was 19 and had 49 followers when i started.\n\n" + LINK,

    "the reason most people never sell a digital product:\n\n"
    "they ask \"what could i sell\" instead of \"what have i already solved\".\n\n"
    "the first invites you to invent something. inventing is hard and usually wrong.\n"
    "the second asks you to notice something. noticing takes an hour.\n\n"
    "six questions that end the loop:\n\n"
    "what have people asked me for help with recently\n"
    "what did i figure out this year that confused me last year\n"
    "what do i have a folder of\n"
    "what do i do faster than people around me\n"
    "what did i pay for that was almost good\n"
    "what have i explained more than twice\n\n"
    "whatever survives, pick the most boring one. boring means specific.\n\n" + LINK,

    "things i believed that cost me months:\n\n"
    "\"i need a laptop\" — built the whole thing on a phone\n"
    "\"i need an audience\" — most buyers never followed me first\n"
    "\"i need to show my face\" — not one buyer has seen it\n"
    "\"i need it to be perfect\" — my best seller was nearly binned\n"
    "\"i need to be an expert\" — i was one step ahead, that was enough\n\n"
    "every one of those was an excuse wearing a reasonable outfit.\n\n" + LINK,

    "how a digital product actually makes money while you sleep. mechanically:\n\n"
    "someone reads a post at 3am\n"
    "taps the link in the bio\n"
    "lands on a product page that answers one question\n"
    "pays\n"
    "gumroad emails them the file automatically\n"
    "you find out in the morning\n\n"
    "no call. no dm. no negotiation. no inventory.\n\n"
    "the entire job is steps one and three. the rest is infrastructure someone\n"
    "else already built for you.\n\n" + LINK,

    "pricing a first digital product, honestly:\n\n"
    "go lower than people tell you.\n\n"
    "a first product's job is your first buyers, not your best margin. a buyer\n"
    "is worth far more than a browser, because buyers buy again and browsers\n"
    "mostly do not start.\n\n"
    "always anchor. set a higher list price and discount to your real one. a\n"
    "flat number has nothing to be judged against.\n\n"
    "keep the anchor near double. four times looks like a fire sale and makes\n"
    "people wonder what is wrong with it.\n\n"
    "raise it after 10 sales and 2 pieces of feedback.\n\n" + LINK,

    "the boring truth about selling online:\n\n"
    "most people do not have a content problem. they have a finishing problem.\n\n"
    "i spent five days choosing what to make and two days making it. the\n"
    "choosing was the hard part, and it was hard because i kept trying to\n"
    "invent a product instead of noticing a problem.\n\n"
    "if you are stuck, you are probably not stuck on the work.\n\n" + LINK,

    "why your posts get likes and no sales:\n\n"
    "you are posting the product, not the problem. nobody wakes up wanting a pdf.\n"
    "your profile does not say what you do. they tapped your name and left.\n"
    "there is no obvious next step. if they have to hunt for the link they will not.\n"
    "you only post proof. proof convinces people who already believe you.\n"
    "you are talking to everyone, which reaches nobody.\n\n"
    "fix the profile before you write another post. it is where every click lands.\n\n" + LINK,

    "everything i used to build and launch a digital product. all free:\n\n"
    "google docs — wrote it first, designed it second\n"
    "canva — made the actual product, free plan\n"
    "gumroad — takes the payment, sends the file, handles refunds\n"
    "a link-in-bio page — because bios only get one link\n"
    "my phone's notes app — every hook that half worked\n\n"
    "that is the entire stack. the barrier was never the tools.\n\n" + LINK,

    "what happens after you launch, which nobody writes about:\n\n"
    "there will be a day in the first week where nothing happens. no sales,\n"
    "barely any engagement.\n\n"
    "that is the moment most people change everything. changing everything is\n"
    "how you never find out whether anything worked.\n\n"
    "post anyway. reply to every comment. ask the people who bought why they\n"
    "bought, and use their words on your page.\n\n"
    "change one thing at a time or you learn nothing.\n\n" + LINK,

    "a digital product you could build this weekend, from most to least obvious:\n\n"
    "a checklist for something you already do properly\n"
    "a notion template you built for yourself, cleaned up\n"
    "a swipe file — 20 examples and why each works\n"
    "a 30-day plan, one page per day\n"
    "a spreadsheet that does one annoying calculation\n"
    "scripts for the messages people freeze up writing\n"
    "a beginner guide to what you learned last month\n\n"
    "none of these need a following. i started with 49.\n\n" + LINK,

    "faceless works. mechanically, here is why:\n\n"
    "people are not buying you. they are buying the outcome.\n\n"
    "they need to believe you have actually done the thing, and a screenshot\n"
    "does that better than a face does. my product page has no photo of me,\n"
    "no name, and no voice.\n\n"
    "what it does have is a specific problem, a specific solution, and proof.\n\n"
    "the anonymity forces the product to carry the argument. that is a feature.\n\n" + LINK,

    "the first sale is not a money event, it is an information event.\n\n"
    "before it, everything is theory. you are guessing whether the thing you\n"
    "made is worth anything to anyone.\n\n"
    "after it, you know. and everything after that is repetition.\n\n"
    "which is why pricing low at the start is not weakness. you are buying\n"
    "information about whether this works, and it is cheap at the price.\n\n" + LINK,
]


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = json.load(open(HERE / "queue.json", encoding="utf-8"))
    targets = []
    for e in q:
        if e.get("status") != "pending":
            continue
        for t in (e.get("targets") or []):
            if t.get("platform") == "x":
                targets.append((e, t))
    targets.sort(key=lambda p: p[0]["scheduled_time"])
    print(f"X targets to give long-form text: {len(targets)}")
    for i, (entry, t) in enumerate(targets):
        t["text"] = POSTS[i % len(POSTS)]
    json.dump(q, open(HERE / "queue.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    lens = [len(p) for p in POSTS]
    print(f"  {len(POSTS)} unique long-form posts, {min(lens)}-{max(lens)} chars")
    print(f"  every one ends in the product link, which post_x moves to a reply")
    print(f"  cost per post: $0.015 + $0.015 for the link reply = $0.03")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
