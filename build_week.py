"""
Builds one week of queue entries on the new format split (2026-08-05 reset).

WHAT CHANGED AND WHY
  Until now every post was a single short post - the format that averages 729
  views in the July data, against 12,899 for a long-form thread. We had never
  published a thread because post_text() had no reply_to_id.

  Weekday (6):  3 threads + 2 screenshots + 1 short
  Weekend (8):  3 threads + 4 screenshots + 1 short   <- Sat/Sun reach ~35% higher

  Thread topics run 2 utility : 1 identity. Utility lists get saved and shared
  (reach); identity lists get replies (growth, and replies tracked growth at every
  rung of the July report). Topics stay in money/beginner territory - broad enough
  to travel, close enough that the followers gained can actually buy.

  TDS mirrors MAIN with an angle shift, 10 min behind, so the two are comparable.

Run:  python build_week.py            (writes week_batch.json)
      python validate_content.py week_batch.json
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
TZ = timezone(timedelta(hours=2))          # Berlin CEST; US Eastern = Berlin - 6

# Slots chosen for US hours (see CLAUDE.md 4.2). Threads take the slots with the
# most runway ahead of them; the 01:30 US-prime slot always gets a receipt.
# 2 threads on weekdays, 3 at the weekend. Not 3 flat: 3/day is 21 unique threads
# a week per account, and a repeated thread is exactly the duplication the content
# reset was about. 16 real ones beats 21 slots filled with reruns.
WEEKDAY = [("14:00", "thread"), ("16:30", "image"), ("20:00", "image"),
           ("22:00", "short"),  ("23:30", "thread"), ("01:30", "image")]
WEEKEND = [("14:00", "thread"), ("16:30", "image"), ("18:00", "image"),
           ("20:00", "thread"), ("22:00", "short"), ("23:00", "image"),
           ("23:30", "thread"), ("01:30", "image")]

CTA = ("getting a lot of dms asking how this works.\n\n"
       "easier to put it in one place than answer it fifty times. it's the whole "
       "thing - what to sell, how to build it, how to set the store up so it runs "
       "on its own.\n\n"
       "https://digitalstackr.gumroad.com/l/faceless-digital-empire")

# ---------------------------------------------------------------- threads
# Every hook is one declarative line. Every list item is concrete. No maxims.
THREADS = [
    {"kind": "utility", "parts": [
        "10 DIGITAL PRODUCTS YOU CAN BUILD IN A WEEKEND.\n\n(all of these are just a doc and a bit of thought)",
        "1. a checklist for something you already do properly.\npeople pay to skip the part where they forget a step.",
        "2. a notion template.\nbuild the thing you built for yourself, then clean it up.",
        "3. a swipe file.\n20 examples of something that works, with a line on why each one works.",
        "4. a 30-day plan.\none page per day. the value is that they don't have to decide.",
        "5. a spreadsheet that does one annoying calculation.\nboring sells.",
        "6. a starter pack of templates for one specific tool.\ncanva, capcut, pick one.",
        "7. a swipe of scripts.\ndms, emails, replies. anything people freeze up writing.",
        "8. a swipe of hooks for one platform.\nnarrow beats broad every time.",
        "9. a beginner guide to the thing you learned last month.\nyou only need to be one step ahead.",
        "10. a bundle of 3 things you already made.\nsame work, higher price.\n\nnone of these need a following. i started with 49."]},
    {"kind": "identity", "parts": [
        "10 THINGS I COULDN'T AFFORD AT 18.",
        "1. saying no to work i didn't want.",
        "2. a laptop that didn't take two minutes to open a browser tab.",
        "3. being ill without doing the maths on it.",
        "4. courses from people who'd actually done the thing.",
        "5. saying yes when friends went out.",
        "6. time. every hour had to turn into something.",
        "7. being wrong slowly. mistakes had to be cheap.",
        "8. the version of anything that lasts longer.",
        "9. not checking my balance before ordering.",
        "10. patience.\n\ni built a digital product because it was the only thing i could start with nothing. that part is still true."]},
    {"kind": "utility", "parts": [
        "7 REASONS YOUR POSTS GET VIEWS BUT NO SALES.",
        "1. you're posting the product, not the problem.\nnobody wakes up wanting a pdf.",
        "2. your profile doesn't say what you do.\nthey tapped your name, read nothing, left.",
        "3. there's no obvious next step.\nif they have to search for the link, they won't.",
        "4. you only post proof.\nproof convinces people who already believe you.",
        "5. the price isn't the problem, the trust is.\ncheap and expensive both fail without it.",
        "6. you're talking to everyone.\n'anyone who wants to make money online' reaches nobody.",
        "7. you stopped before the boring part.\nmost of my sales came after the week i nearly quit."]},
    {"kind": "utility", "parts": [
        "EVERY TOOL I USED TO BUILD MY FIRST DIGITAL PRODUCT.\n\n(free, all of it)",
        "1. canva - made the actual product. free plan.",
        "2. google docs - wrote it first, designed it second. doing that backwards wastes days.",
        "3. gumroad - takes the payment, sends the file, handles refunds. i do nothing.",
        "4. beacons - one page holding the links, because bios only get one.",
        "5. threads - the only place i posted. one platform properly beats four badly.",
        "6. my phone's notes app - every hook that half-worked, kept in one place.",
        "7. a screen recorder - so i could see what my own page looked like to a stranger.\n\nthat's the entire stack. the barrier was never the tools."]},
    {"kind": "identity", "parts": [
        "9 THINGS I STOPPED DOING WHEN I DECIDED TO ACTUALLY BUILD SOMETHING.",
        "1. researching instead of starting. i knew enough by week two.",
        "2. redesigning the cover. nobody bought it for the cover.",
        "3. waiting to feel ready. that feeling never turned up.",
        "4. checking what everyone else was posting before i posted.",
        "5. explaining what i was doing to people who didn't ask.",
        "6. treating a quiet day as evidence it wouldn't work.",
        "7. rewriting the same post instead of publishing three.",
        "8. calling it a side project. that's permission to drop it.",
        "9. comparing my week one to someone's year three.\n\nnone of that was hard. i just had to stop."]},
    {"kind": "utility", "parts": [
        "8 THINGS NOBODY TELLS BEGINNERS ABOUT SELLING DIGITAL PRODUCTS.",
        "1. the first sale takes longer than the next twenty.",
        "2. your best post will not be the one you were proud of.",
        "3. people buy at 3am. the store working without you is the whole point.",
        "4. cheap doesn't mean easy to sell. trust is the price, not the number.",
        "5. most buyers never follow you first. they see one post and decide.",
        "6. refunds happen and they are fine. gumroad handles it, you move on.",
        "7. the product gets better after people use it, not before.",
        "8. consistency beats quality for the first 90 days. then it flips."]},
    {"kind": "identity", "parts": [
        "10 THINGS I'D TELL MYSELF AT 49 FOLLOWERS.",
        "1. the number is not the business. sales came before the audience did.",
        "2. post the thing you think is too obvious. that one lands.",
        "3. nobody is watching closely enough for a bad post to matter.",
        "4. one platform. properly.",
        "5. write like you're explaining it to one person, because you are.",
        "6. finish the product before you're happy with it.",
        "7. screenshots of small numbers convert better than big ones.",
        "8. answer every comment for the first year.",
        "9. don't announce plans. announce things that already exist.",
        "10. keep going through the part where it's embarrassing. that's the filter."]},
    {"kind": "utility", "parts": [
        "8 WAYS TO FIND SOMETHING TO SELL WHEN YOU THINK YOU KNOW NOTHING.",
        "1. what do people already ask you for help with. that's the list.",
        "2. what did you figure out this year that confused you last year.",
        "3. what do you have a folder of. templates, screenshots, links.",
        "4. what do you do faster than the people around you.",
        "5. search your niche and read the 2-star reviews. that's a product brief.",
        "6. what did you pay for that was almost good.",
        "7. what would have saved you six months.",
        "8. what have you explained twice this month.\n\nnone of these need expertise. they need you to have been paying attention."]},
    {"kind": "identity", "parts": [
        "7 THINGS THAT CHANGED WHEN I STOPPED CARING IF IT LOOKED PROFESSIONAL.",
        "1. i shipped in days instead of weeks.",
        "2. people replied like i was a person, because i was.",
        "3. the posts got shorter and did better.",
        "4. i stopped rewriting things nobody was going to read twice.",
        "5. i stopped comparing my page to companies with teams.",
        "6. mistakes cost an hour instead of a month.",
        "7. i actually enjoyed it, which is the only reason i kept going."]},
    {"kind": "utility", "parts": [
        "9 THINGS TO FIX ON YOUR PROFILE BEFORE POSTING ANYTHING ELSE.",
        "1. your bio says what you do, not what you are.",
        "2. one link. not four. they only click one anyway.",
        "3. a pinned post that shows a result, not an introduction.",
        "4. the same name people can actually search for.",
        "5. a picture that reads at thumbnail size.",
        "6. no 'coming soon'. nobody sets a reminder.",
        "7. proof visible without scrolling.",
        "8. one clear thing to do next.",
        "9. open it on someone else's phone. it's never what you think it is."]},
    {"kind": "utility", "parts": [
        "7 MISTAKES THAT COST ME MY FIRST TWO MONTHS.",
        "1. building the product before checking anyone wanted it.",
        "2. posting on four platforms badly instead of one properly.",
        "3. copying someone else's price without knowing why they picked it.",
        "4. treating every quiet day as a verdict.",
        "5. writing for people already doing this instead of people starting.",
        "6. redesigning instead of publishing.",
        "7. not asking the people who bought why they bought.\n\nall seven were free to fix. i just didn't know."]},
    {"kind": "identity", "parts": [
        "8 THINGS THAT ARE TRUE AT 19 THAT NOBODY SAYS OUT LOUD.",
        "1. everyone assumes you're guessing. mostly you are.",
        "2. having no money makes you decide faster.",
        "3. nobody your age is as sorted as their posts suggest.",
        "4. adults take you seriously about 30 seconds after you show them something real.",
        "5. the time you have is the only advantage you actually own.",
        "6. being underestimated is easier than being watched.",
        "7. you can start something badly and fix it later. that's most of it.",
        "8. nobody is coming to tell you it's allowed."]},
    {"kind": "utility", "parts": [
        "10 POSTS THAT SELL WITHOUT EVER MENTIONING A PRODUCT.",
        "1. the mistake you made and what it cost.",
        "2. the thing you believed a year ago that was wrong.",
        "3. a number, and how you felt about it.",
        "4. the boring habit that actually did it.",
        "5. the objection you get most, answered honestly.",
        "6. what you'd do differently starting today.",
        "7. the part everyone skips.",
        "8. a small win that felt bigger than it was.",
        "9. what nobody warned you about.",
        "10. the day you nearly stopped.\n\npeople buy after they trust you. none of these ask for anything."]},
    {"kind": "utility", "parts": [
        "6 THINGS TO DO IN YOUR FIRST WEEK, IN ORDER.",
        "1. pick one problem you've personally solved. one. write it at the top of a doc.",
        "2. list the ten steps you took to solve it. that's your contents page.",
        "3. write it plainly. no intro, no mindset chapter, no filler.",
        "4. put it in canva. one hour, not one week.",
        "5. upload to gumroad. price it low. you can raise it later.",
        "6. post about the problem every day. not the product.\n\nthat's the whole first week. most people spend it choosing a name."]},
    {"kind": "identity", "parts": [
        "7 THINGS I THOUGHT WOULD HAPPEN WHEN I MADE MY FIRST SALE.",
        "1. i thought i'd feel finished. it lasted about an hour.",
        "2. i thought people would ask how. they didn't, for weeks.",
        "3. i thought it meant the hard part was done. it was the easiest part.",
        "4. i thought i'd want to tell everyone. i told nobody.",
        "5. i thought the next one would come fast. it took six days.",
        "6. i thought $27 would feel small. it didn't.",
        "7. i thought i'd stop checking. i still check."]},
    {"kind": "utility", "parts": [
        "8 SIGNS THE THING YOU'RE BUILDING WON'T SELL.",
        "1. you can't say who it's for in one sentence.",
        "2. it solves a problem people don't know they have.",
        "3. you're describing it with adjectives instead of outcomes.",
        "4. it needs explaining before it's wanted.",
        "5. you've been building it for more than three weeks.",
        "6. you'd feel awkward showing it to someone specific.",
        "7. everything about it is 'comprehensive'.",
        "8. you're more excited about the branding than the contents.\n\nall of these are fixable. none of them fix themselves."]},
]

# ------------------------------------------------------- screenshots + shorts
# Figures MUST match the attached image exactly (image_manifest.json).
IMAGES = [
    ("IMG_4397.PNG", "$382 this month from 104 people.\nnot life changing. but it's the first money i've made that didn't need me awake for it."),
    ("gumroad notification screenshot.PNG", "a sale came in at 3:33am.\nphone face down, dead asleep. woke up to it already done."),
    ("Untitled design (10).png", "$640.80 from 32 people.\nzero ads. i genuinely do not know how to run them."),
    ("IMG_3944.PNG", "$181.30.\ni was walking home. it had already happened without me."),
    ("IMG_4395.PNG", "someone bought the $27 guide at 2:24pm.\ni was doing something else entirely. that still feels strange."),
    ("Untitled design (17).png", "$201 from 19 people.\nquiet day. i'll take a quiet day that still pays."),
    ("Untitled design (8).png", "$224.52 from 24 people.\nsix months ago i'd have said that was made up."),
    ("IMG_4274.PNG", "someone paid $147 for me to build their store for them.\ni'm 19. that one took a minute to process."),
    ("Untitled design(6).png", "88 separate people decided this was worth paying for.\n$735.29. my phone was in a bag under a desk for most of it. 🤍"),
    ("Untitled design (11).png", "$739.50 from 65 people.\n65 strangers trusted a guide written by a teenager."),
    ("gumroad sales notifications.PNG", "$27, again.\nthe same guide i almost didn't publish because it felt too simple."),
    ("Untitled design(4).png", "$856.23 from 92 people.\nno face, no name, no ads. just a doc that solved one thing."),
    ("IMG_3795.PNG", "someone paid $50 for two weeks of my time back when that was the price.\n19 years old and somebody trusted me with their launch."),
    ("Untitled design (5).png", "the whole business is on this phone.\nno office, no laptop, no staff. just the one screen."),
    # Second pass over the same screenshots, different angle each time. Images may
    # repeat after IMAGE_REUSE_DAYS; captions never repeat.
    ("IMG_4397.PNG", "104 people bought something i made in canva.\nstill the part i find hardest to explain to people at home."),
    ("Untitled design (10).png", "someone told me this market was saturated.\n$640.80 from 32 people that same week."),
    ("IMG_3944.PNG", "$181.30.\ni checked my phone expecting a bill."),
    ("Untitled design (8).png", "$224.52 from 24 people.\nnone of them asked how old i was."),
    ("gumroad notification screenshot.PNG", "$27 at 3:33am.\nthe store doesn't know what time it is and that's the entire point."),
    ("Untitled design (17).png", "$201 from 19 people.\nsmall enough that i think anyone reading this could do it. that's why i'm posting it."),
    ("IMG_4274.PNG", "$147 for a done-for-you store.\ni built someone their whole business while mine ran itself."),
    ("Untitled design (11).png", "$739.50 from 65 people.\nno face, no ads, no team. i keep waiting for the catch."),
    ("Untitled design(4).png", "$856.23 from 92 people.\ni started this with nothing but a phone and a lot of free evenings."),
]

# TDS runs the SAME screenshot with a different angle on it. MAIN states the
# result; TDS narrates the moment around it. Same proof, same slot order, so any
# gap in performance is the ANGLE, not the content - which is the thing we
# actually want to learn. Threads themselves stay identical across both accounts:
# that test is about the format, and changing two variables at once tells us
# nothing.
IMAGES_TDS = [
    "$382 this month. 104 people.\nchecked it twice on the way to class because it didn't look real.",
    "3:33am. phone face down.\nwoke up and it had already happened without me.",
    "$640.80 from 32 people.\nsomeone asked what my ad budget is. i don't have one.",
    "$181.30 while i was out.\nfirst time money turned up that i hadn't traded an hour for.",
    "$27, 2:24pm.\ni was in the middle of something else. it still went through.",
    "$201 from 19 people.\nnot a big day. still a day that paid.",
    "$224.52 from 24 people.\nsix months ago this screenshot would have annoyed me.",
    "$147 for a store i built for someone else.\nthey trusted a 19 year old with their launch.",
    "$735.29 from 88 people.\nphone was in my bag the whole time. 🤍",
    "$739.50 from 65 people.\ni've refreshed it about four times.",
    "$27 again.\nsame guide. the one that felt too simple to charge for.",
    "$856.23 from 92 people.\nnone of them know my name and it doesn't matter.",
    "$50 for two weeks of my time, back when that was the price.\nsomebody's launch, in my hands, at 19.",
    "the entire business fits on this screen.\nno office. no team. no laptop.",
    "104 people. one guide.\ni made it in canva on a weekend and almost binned it.",
    "somebody told me digital products were finished.\n$640.80 that same week, from 32 people.",
    "$181.30 turned up and my first thought was that something had gone wrong.",
    "$224.52 from 24 people.\nnobody asked my age. nobody asked for my face.",
    "$27 at 3:33am.\nthe store kept working while i was unconscious.",
    "$201 from 19 people.\nposting the small ones because those are the believable ones.",
    "$147 to build someone else's store.\nmine was running in another tab.",
    "$739.50 from 65 people.\nstill waiting for someone to tell me it's a mistake.",
    "$856.23 from 92 people.\nstarted with a phone and empty evenings. that's genuinely it.",
]

SHORTS = [
    "i almost didn't publish the guide because it felt too simple.\nsimple is what people were stuck on.",
    "spent three weeks making a product nobody wanted, then two days making one that sold.\nthe difference was asking first.",
    "the first sale took six weeks. the second took a day.\nnobody warns you the gap is that uneven.",
    "i still write posts i think are too obvious. those are the ones that land.",
    "no ads. no face. no idea what i was doing for the first month.",
    "the store made money while i was in a lecture. that's the entire pitch.",
    "quiet week. still built. that's most of it, honestly.",
]


def build(start_date, days=7, start_id=2000):
    entries, eid = [], start_id
    ti = ii = si = 0
    for d in range(days):
        day = start_date + timedelta(days=d)
        slots = WEEKEND if day.weekday() >= 5 else WEEKDAY

        for hhmm, kind in slots:
            hh, mm = map(int, hhmm.split(":"))
            when = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if hh < 6:                      # 01:30 belongs to the following morning
                when += timedelta(days=1)

            entry = {"id": eid, "scheduled_time": when.isoformat(), "status": "pending"}

            tds_text = None
            if kind == "thread":
                t = THREADS[ti % len(THREADS)]; ti += 1
                entry["thread_parts"] = t["parts"]
                entry["targets"] = [{"platform": "threads", "account": "MAIN"}]
                # Utility threads travel furthest, so those carry the CTA if they pop.
                if t["kind"] == "utility":
                    entry["auto_plug"] = {"status": "pending", "account": "MAIN", "text": CTA}
            elif kind == "image":
                idx = ii % len(IMAGES)
                img, cap = IMAGES[idx]; ii += 1
                entry["text"] = cap
                entry["image_file"] = img
                entry["targets"] = [{"platform": "threads", "account": "MAIN"},
                                    {"platform": "x"}]
                tds_text = IMAGES_TDS[idx]
            else:
                entry["text"] = SHORTS[si % len(SHORTS)]; si += 1
                entry["targets"] = [{"platform": "threads", "account": "MAIN"},
                                    {"platform": "x"}]

            entries.append(entry); eid += 1

            # TDS mirror, 10 minutes behind. Same content, so a difference in
            # performance is a difference in AUDIENCE, not in what was posted.
            tds = json.loads(json.dumps(entry))
            tds["id"] = eid; eid += 1
            tds["scheduled_time"] = (when + timedelta(minutes=10)).isoformat()
            tds["targets"] = [{"platform": "threads", "account": "TDS"}]
            if tds_text:
                tds["text"] = tds_text     # same screenshot, different angle on it
            if tds.get("auto_plug"):
                tds["auto_plug"] = {"status": "pending", "account": "TDS", "text": CTA}
            entries.append(tds)

    return entries


if __name__ == "__main__":
    start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    batch = build(start)
    out = HERE / "week_batch.json"
    out.write_text(json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")
    threads = sum(1 for e in batch if e.get("thread_parts"))
    print(f"{len(batch)} entries -> {out.name}")
    print(f"  {threads} threads, {sum(1 for e in batch if e.get('image_file'))} screenshots, "
          f"{len(batch) - threads - sum(1 for e in batch if e.get('image_file'))} shorts")
    print(f"  {start.date()} -> {(start + timedelta(days=6)).date()}")
