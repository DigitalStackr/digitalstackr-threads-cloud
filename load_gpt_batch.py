"""
Loads the ChatGPT-written batch into the queue, with images and real figures.

WHAT CHATGPT DID AND DID NOT DO
  It wrote 40 MAIN + 40 TDS captions inside the five measured structures, left
  every money figure as [FIGURE], and produced ZERO near-duplicates (max pairwise
  similarity 0.38 against a 0.82 limit). That is better discipline than my own
  batches managed this week.

  What it could not do is choose the screenshot or fill the number - the figure
  has to match the attached image exactly, and only image_manifest.json knows
  what each screenshot actually shows. That mapping is done here.

DROPPED (2 of 40)
  "seeing an order bump sitting underneath the original order"  - no screenshot
  "there's still a 4.9 rating sitting beside the product"       - no screenshot
  Both are strong angles. They come back the moment those two screenshots exist.

RARE-TIER BUDGET
  validate_content caps 'rare' (four-figure) images at 2 per account per calendar
  month. This batch spends exactly that budget and no more.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
TZ = timezone(timedelta(hours=2))

WEEKDAY = ["14:00", "16:30", "20:00", "22:00", "23:30", "01:30"]
WEEKEND = ["14:00", "16:30", "18:00", "20:00", "22:00", "23:00", "23:30", "01:30"]

# (image, figure_token, MAIN, TDS)
# figure_token replaces [FIGURE]; it must appear in that image's manifest numbers.
BATCH = [
 ("IMG_3944.PNG", "$181.30",
  "ITS OFFICIAL!!!!!\n[FIGURE] landed and my phone was still plugged into the wall.\n\nbuilt this faceless. built it from a phone. started with nobody watching.\n\nstill weird seeing it become real \U0001f90d",
  "the charging cable was still hanging off my phone when i opened the payout screen.\n\n[FIGURE].\n\ni just sat there looking at it.\n\nthe part i thought would hold me back was being faceless."),

 ("IMG_4397.PNG", "$382",
  "okay this one got me.\n\n[FIGURE].\n\nand the gumroad dashboard still looks like the same little page i opened when nobody was buying.\n\nvery very grateful for this.",
  "i refreshed the dashboard expecting basically nothing.\n\nthen [FIGURE] was sitting there.\n\nsame dashboard.\n\ncompletely different feeling now \U0001f979"),

 ("Untitled design (8).png", "$224.52",
  "I CAN FINALLY SAY IT!!!!!\n\n[FIGURE].\n\nfrom something i almost kept sitting unfinished inside canva.\n\npublishing it was the scary part.",
  "the canva file looked so unimpressive before i published it.\n\njust another digital product sitting on my screen.\n\nnow i'm looking at [FIGURE] because i actually pressed publish."),

 ("Untitled design (10).png", "$640.80",
  "this is officially getting ridiculous \U0001f62d\U0001f4b8\n\n[FIGURE].\n\nfrom a faceless account that started with zero followers and a phone.\n\ni really almost talked myself out of starting this.",
  "my home screen still looks painfully normal.\n\nthreads. canva. checkout.\n\nthen i open the numbers and see [FIGURE].\n\nthat's the part my brain still hasn't caught up with."),

 ("Untitled design (17).png", "€552.61",
  "i'm keeping this screenshot forever.\n\n[FIGURE].\n\nall because i stopped treating my bio link like decoration and actually built something behind it.",
  "the link in my bio looks like such a small thing on the screen.\n\ntap it and there's an entire little business behind it now.\n\n[FIGURE].\n\ni'm glad i kept building."),

 ("Untitled design(6).png", "$735.29",
  "not sure when this stopped feeling like an experiment.\n\n[FIGURE].\n\nmaybe somewhere between posting into silence and watching real people buy.\n\n\U0001f90d",
  "i was staring at the notification panel when i checked the sales.\n\n[FIGURE].\n\nthere used to be days where the only notification i wanted was one person buying."),

 ("Untitled design (11).png", "$739.50",
  "THIS ACTUALLY WORKED.\n\n[FIGURE].\n\nfrom a product delivered automatically while i'm still doing everything from my phone.\n\nthat's all i wanted when i started.\n\nproof.",
  "the delivery page does its job without me touching anything.\n\nbuyer pays.\n\nproduct arrives.\n\nthen i look at my phone and see [FIGURE].\n\nsimple still feels better than complicated."),

 ("Untitled design(4).png", "$856.23",
  "i genuinely smiled at this one.\n\n[FIGURE].\n\nthere's a folder full of hooks on my phone that started as random notes.\n\nnow those notes help sell an actual product.",
  "i opened the hook vault after checking the sale screen.\n\nthat folder used to just be ideas i didn't know what to do with.\n\nnow the dashboard says [FIGURE]."),

 ("IMG_4395.PNG", "$27",
  "okay. officially proud of this.\n\n[FIGURE].\n\nno face on the sales page.\n\nno voice in the product.\n\njust something useful and someone trusting it.",
  "the product thumbnail has never had my face on it.\n\nbuyers still clicked.\n\nbuyers still trusted it.\n\n[FIGURE].\n\nfaceless was never the dealbreaker i imagined."),

 ("gumroad sales notifications.PNG", "$27",
  "I'M NEVER GETTING USED TO THIS \U0001f62d\U0001f4b8\n\n[FIGURE].\n\ni opened threads to post like normal and ended up opening a payment notification instead.\n\nwhat a strange little business.",
  "my thumb was literally over the app when the payment notification caught my eye.\n\n[FIGURE].\n\ni forgot what i was about to post."),

 ("IMG_4274.PNG", "$147",
  "someone paid [FIGURE] for something i built without ever knowing my name.\n\nthat's the part i keep thinking about.\n\nthe checkout page did all the introducing for me.",
  "a buyer reached the checkout button without seeing my face, hearing my voice or knowing who i am.\n\nthen paid [FIGURE].\n\nfaceless really does force the product to speak for itself."),

 ("gumroad notification screenshot.PNG", "$27",
  "someone just paid [FIGURE] after finding me through a tiny post.\n\nnot a sales call.\n\nnot a huge launch.\n\na post written on a phone.",
  "i looked back at the draft after the order came through.\n\nnothing fancy about it.\n\nsomeone read those few lines, tapped the bio and paid [FIGURE]."),

 ("IMG_3795.PNG", "$50",
  "a complete stranger trusted me with [FIGURE].\n\nthe weird part is my inbox was completely quiet.\n\nthey didn't need convincing first.",
  "no long conversation sitting in my inbox.\n\nno back-and-forth.\n\njust an order confirmation for [FIGURE].\n\nsometimes the product page answers enough."),

 ("IMG_1747.PNG", "$17.16",
  "someone paid [FIGURE] and immediately got the product without waiting for me.\n\nthat little delivery email is doing more work than people realise.",
  "the buyer's delivery email had already gone out before i even noticed the order.\n\n[FIGURE].\n\nthat's when digital products started making sense to me."),

 ("IMG_2521.PNG", "$27",
  "someone saw my little faceless account and decided this was worth [FIGURE].\n\ni'm looking at the order confirmation thinking about how easily i could've never started.\n\n\U0001f90d",
  "the order confirmation has a stranger's purchase on it.\n\nmy face is nowhere.\n\nmy name is nowhere.\n\n[FIGURE] still changed hands because the product made sense to them."),

 ("Untitled design (8).png", "$224.52",
  "a buyer paid [FIGURE] from the same checkout i kept tweaking on my phone.\n\nthat's the part nobody sees.\n\nyou stare at a button forever.\n\nthen eventually somebody presses it.",
  "i spent way too much time looking at that checkout button when i built the page.\n\nthen somebody actually tapped it.\n\n[FIGURE].\n\ntiny details feel different once a real buyer uses them."),

 ("Untitled design (10).png", "$640.80",
  "someone trusted [FIGURE] to a product that started as a blank document.\n\nthat's still the cleanest explanation i have for why i love this business.",
  "the first version was literally an empty document on a screen.\n\nnow there's a receipt for [FIGURE] attached to what it became.\n\npublishing changes things."),

 ("gumroad notification screenshot.PNG", "$27",
  "my product sold while my phone was face down.\n\n[FIGURE].\n\nno refresh.\n\nno DM.\n\nno convincing anyone in real time.\n\nthat still feels illegal \U0001f62d",
  "i flipped my phone over and the sale was already there.\n\n[FIGURE].\n\nnothing dramatic happened.\n\nthat's probably why the moment felt so good."),

 ("Untitled design (11).png", "$739.50",
  "i closed the tab.\n\nthe product sold anyway.\n\n[FIGURE].\n\ndigital products made a lot more sense after moments like this.",
  "the browser wasn't even open anymore when the order came through.\n\nthen i checked later.\n\n[FIGURE].\n\nthe store doesn't really care whether i'm staring at it."),

 ("Untitled design(6).png", "$735.29",
  "i was eating before i checked anything.\n\nopened my phone after.\n\n[FIGURE].\n\napparently the store did not need me hovering over it.",
  "my plate was still on the table when i finally checked the dashboard.\n\n[FIGURE].\n\ni love that the boring little moments are usually when this hits hardest."),

 ("IMG_3909.PNG", "$27",
  "my phone was on the lock screen.\n\nsomebody was already buying.\n\n[FIGURE].\n\nthis is why i wanted a digital product in the first place.",
  "the lock screen lit up with an order i wasn't waiting for.\n\n[FIGURE].\n\ni remember when i used to unlock my phone hoping there'd be one."),

 ("Untitled design(4).png", "$856.23",
  "i wasn't writing content.\n\ni wasn't checking the dashboard.\n\nthe checkout still processed [FIGURE].\n\nquiet systems beat constant chasing.",
  "my draft was sitting untouched when the order happened.\n\ni wasn't selling anything in that exact moment.\n\n[FIGURE] still came through.\n\nthat's the bit i wanted."),

 ("IMG_4397.PNG", "$382",
  "the sale happened while canva was closed.\n\n[FIGURE].\n\nsomething i already finished kept doing its job without another edit.",
  "there wasn't even a canva tab open when i noticed the purchase.\n\njust a finished product doing what finished products can do.\n\n[FIGURE]."),

 ("IMG_3944.PNG", "$181.30",
  "i put the phone down.\n\nsomeone bought.\n\n[FIGURE].\n\nvery difficult to explain how satisfying that feels after starting from zero.\n\n\U0001f90d",
  "my phone was sitting beside me when the order arrived.\n\ni wasn't watching the screen.\n\nthen there it was.\n\n[FIGURE]."),

 ("IMG_4395.PNG", "$27",
  "the app was closed.\n\ncheckout wasn't.\n\n[FIGURE].\n\nprobably my favourite thing i've learned from building this.",
  "the icon was just sitting on my home screen when the payment came through.\n\n[FIGURE].\n\nthe post had already done its part."),

 ("3.9k gumroad ss.png", "$3,937.55",
  "19 years old.\n\n[FIGURE].\n\nfrom digital products sold behind a faceless account.\n\nno personal brand.\n\nno face reveal coming.\n\ni built around the thing everyone told me i'd need.",
  "my phone case has seen this entire business get built.\n\nstarted at zero followers.\n\nstayed faceless.\n\nnow i'm looking at [FIGURE].\n\nturns out anonymity wasn't the problem."),

 ("Untitled design(4).png", "$856.23",
  "no face.\n\nno voice.\n\n[FIGURE].\n\npeople told me trust would be impossible without showing who i am.\n\nso i made the product page earn the trust instead.",
  "there isn't a selfie anywhere on the checkout page.\n\nthere never will be.\n\n[FIGURE] still came through.\n\ni'd rather prove faceless can work than argue about it."),

 ("Untitled design (10).png", "$640.80",
  "started with zero followers.\n\nnow the screen says [FIGURE].\n\ni wasn't early.\n\ni wasn't known.\n\ni just kept giving people a reason to click.",
  "the oldest drafts in my folder were written for basically nobody.\n\ni posted them anyway.\n\nnow there's [FIGURE] on the other side of that decision."),

 ("Untitled design (5).png", None,
  "built from a phone.\n\nthe equipment was never the interesting part.\n\nlearning how to make a stranger care was.",
  "the same little phone keyboard i used at zero is the one i'm typing on now.\n\nnothing glamorous changed.\n\ni just got better at using it."),

 ("Untitled design (17).png", "€552.61",
  "i don't have a personal brand.\n\ni have a product people buy.\n\n[FIGURE].\n\nthat distinction saved me from waiting until i felt comfortable being visible.",
  "my profile picture isn't me.\n\nthe sales page isn't about me.\n\nthe receipt still says [FIGURE].\n\ni built the business around what i was willing to do."),

 ("IMG_4274.PNG", "$147",
  "i never needed everyone to believe this worked.\n\ni needed one buyer to prove it.\n\nnow i'm looking at [FIGURE].\n\nthat's why the first sale changes your brain.",
  "i used to stare at the empty order section wondering if anybody would ever show up.\n\nnow there's [FIGURE] sitting there.\n\none real buyer beats a thousand opinions."),

 ("Untitled design(6).png", "$735.29",
  "faceless.\n\nphone-built.\n\n[FIGURE].\n\ni had plenty of reasons this was supposed to be harder for me.\n\nnone of them could stop someone from clicking buy.\n\n\U0001f62d\U0001f4b8",
  "the sales page still has no creator photo.\n\nthe business still fits on my phone.\n\nand the checkout says [FIGURE].\n\ni'm glad i didn't wait for the perfect setup."),

 ("gumroad sales notifications.PNG", "$27",
  "\"people don't trust faceless accounts\"\n\nsomeone just trusted mine with [FIGURE].\n\nthe product page doesn't even have my photo on it.",
  "\"nobody buys from someone they can't see\"\n\ni read things like that when i started.\n\nthen i open a faceless checkout receipt for [FIGURE].\n\nsome advice ages badly."),

 ("Untitled design (11).png", "$739.50",
  "\"you need a big audience first\"\n\n[FIGURE].\n\nthe buyer didn't even need to follow me before reaching the checkout.\n\nfollowers were never the checkout button.",
  "\"grow first. sell later.\"\n\nglad i ignored that.\n\na stranger went from one post to the bio to a [FIGURE] purchase.\n\nthe follower count wasn't part of the receipt."),

 ("Untitled design (8).png", "$224.52",
  "\"you need a laptop to build this properly\"\n\n[FIGURE].\n\nthe whole setup started on a phone.\n\nstill waiting for the equipment to become the excuse.",
  "\"doing it from your phone isn't serious\"\n\nthen a payment notification for [FIGURE] lands on the exact phone i built it from."),

 ("IMG_3795.PNG", "$50",
  "\"there are too many digital products already\"\n\nsomeone still chose mine.\n\n[FIGURE].\n\nthe product thumbnail didn't need an empty market.\n\nit needed the right buyer.",
  "\"that market is saturated\"\n\ni used to let sentences like that sit in my head.\n\nthen another receipt appears beside my product name.\n\n[FIGURE]."),

 ("IMG_2521.PNG", "$27",
  "\"posting here is a waste of time\"\n\n[FIGURE].\n\ni'm looking at the payment notification that came from somebody finding one of those posts.\n\ni'll keep wasting my time.",
  "\"you're always on this app\"\n\nyeah.\n\nbecause a tiny post can turn into a checkout receipt for [FIGURE] while it's still sitting in my recent tabs."),
]


def build(start_day, days, start_id, now):
    out, eid, i = [], start_id, 0
    for d in range(days):
        day = start_day + timedelta(days=d)
        for hhmm in (WEEKEND if day.weekday() >= 5 else WEEKDAY):
            if i >= len(BATCH):
                return out
            hh, mm = map(int, hhmm.split(":"))
            when = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if hh < 6:
                when += timedelta(days=1)
            if when <= now:
                continue
            img, fig, main, tds = BATCH[i]
            i += 1
            m = main.replace("[FIGURE]", fig) if fig else main
            t = tds.replace("[FIGURE]", fig) if fig else tds
            out.append({"id": eid, "scheduled_time": when.isoformat(), "status": "pending",
                        "image_file": img, "text": m,
                        "targets": [{"platform": "threads", "account": "MAIN"},
                                    {"platform": "x"}]})
            eid += 1
            out.append({"id": eid,
                        "scheduled_time": (when + timedelta(minutes=10)).isoformat(),
                        "status": "pending", "image_file": img, "text": t,
                        "targets": [{"platform": "threads", "account": "TDS"}]})
            eid += 1
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = json.load(open(HERE / "queue.json", encoding="utf-8"))
    now = datetime.now(TZ)
    pend = [e for e in q if e.get("status") == "pending"
            and any(t.get("platform") == "threads" for t in (e.get("targets") or []))]
    start_day = (max(datetime.fromisoformat(e["scheduled_time"]) for e in pend)
                 if pend else now).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    batch = build(start_day, 10, max(e["id"] for e in q) + 1, now)
    print(f"generated {len(batch)} entries ({len(batch)//2} slots)")
    print(f"  {batch[0]['scheduled_time'][:16]} -> {batch[-1]['scheduled_time'][:16]}")
    print(f"  unique captions: {len({e['text'] for e in batch})}")
    json.dump(q + batch, open(HERE / "queue.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    json.dump(batch, open(HERE / "gpt_batch_queued.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
