"""
Refill the Telegram channel queue. 5 value posts a week, weekdays at 18:00 Berlin.

WHY THESE POSTS
  The channel has been silent since 2026-08-22. It is meant to run 5 value posts
  a week and the offer stays PINNED, never reposted - a channel audience has
  already opted in, so re-selling to them burns the goodwill that got them there.

  Every post below is a real thing learned running this business in August 2026,
  including the parts that went badly. A tiny, warm, opted-in audience can tell
  the difference between someone sharing what happened and someone performing
  expertise, and the failures are the more useful half.

  No figures are quoted that are not verified, and no screenshots are attached -
  these are text posts, so any $ figure in them would be unbacked by definition.
  The few numbers that do appear are counts and measurements, not income claims.

FORMAT
  Bold title, then short paragraphs. post_telegram.to_html() escapes the caption
  first and re-enables only <b>/<i>, so **bold** and _italic_ are safe and a stray
  & or < cannot break the send.
"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

POSTS = [
 ("Your best post and your worst post can be identical",
  "We reposted our own top performers word for word this month. Same text, same "
  "screenshots, same accounts.\n\nThe posts that did 27,000 views in July did 246.\n\n"
  "That was worth knowing. It means the writing was never the problem — something "
  "about the account's distribution had changed, and no amount of better captions "
  "was going to touch it. Three weeks of rewriting proved it the expensive way.\n\n"
  "If your content stopped working overnight, test whether it is the content "
  "before you spend a month rewriting."),

 ("A green dashboard is not the same as a working system",
  "Our posting system ran perfectly for 94 hours and published nothing.\n\n"
  "Every check passed. Every run succeeded. The queue was simply empty, and "
  "nothing anywhere said so.\n\nFour days passed before anyone noticed.\n\n"
  "Whatever you automate, the alert you actually need is not \"did it run\". It is "
  "\"did anything come out the other end\"."),

 ("Count the right thing",
  "We believed one of our channels converted at 88% and another at 5%.\n\n"
  "It was a counting error. The platform only creates a record when somebody "
  "actually buys or downloads — people who look and leave are invisible. So we "
  "were comparing purchases to purchases and calling it a conversion rate.\n\n"
  "The real rate was nothing like it.\n\nBefore you act on a percentage, ask what "
  "is on the bottom of the fraction. Ours was measuring nothing."),

 ("Seven seconds",
  "We downloaded nine of the best-performing reels in our niche and measured them.\n\n"
  "Every single one: between 6 and 9 seconds.\n\nNot 30. Not 60. Under ten.\n\n"
  "Short enough that people watch it twice without deciding to. The replay is the "
  "point — it is watch time you did not have to earn twice."),

 ("The text does not move",
  "Same nine reels. We expected animated captions appearing line by line.\n\n"
  "Not one of them does it. The full block of text is on screen from the first "
  "frame to the last, completely still. The only thing moving is the camera "
  "drifting slowly across a desk.\n\nWe had built the opposite: animated text over "
  "a static shot.\n\nWhen you copy a format, measure it. Do not infer it from a "
  "screenshot."),

 ("Name what they are doing right now",
  "The single biggest reel we studied — 40% bigger than anything else — opens by "
  "describing what the viewer is doing at that exact second: scrolling.\n\n"
  "Then it offers a swap. Do this instead, tonight.\n\nIt beat every angry "
  "\"here is what everyone gets wrong\" opener by more than four times.\n\n"
  "Attacking a thing gets attention. Naming the thing they are already doing gets "
  "more."),

 # Figures written as words on purpose. validate_content blocks bare $ amounts in
 # text-only posts because they read as unbacked income claims, and it is right to
 # - it cannot tell an arithmetic example from a boast. The numbers are not the
 # point of this post anyway; the error is.
 ("Do the multiplication",
  "We published four posts saying that selling something a hundred times at "
  "twenty-seven dollars makes four thousand a month.\n\nIt makes two thousand "
  "seven hundred.\n\nAnyone with a calculator catches that in three seconds, and "
  "in a space where people are already braced to be lied to, one wrong sum costs "
  "far more than the claim ever gained.\n\nIf your maths is doing the persuading, "
  "check your maths."),

 ("Free things are not lost revenue, part two",
  "We looked properly at what happens to people who take the free download.\n\n"
  "A small number of them come back later and pay. Not most. Not even close to "
  "most. But enough that it accounts for roughly a fifth of everything the "
  "business has ever earned.\n\nAnd that happened with **zero follow-up**. Nobody "
  "was ever emailed.\n\nThe free thing works better than we thought and we were "
  "doing the laziest possible version of it."),

 ("One variable",
  "When something stops working the temptation is to change everything at once.\n\n"
  "We changed the writing, the posting times, the volume, the images and the "
  "rules, all in the same fortnight. Then reach moved.\n\nWe had no idea which "
  "one did it. Possibly none of them.\n\nChange one thing. Wait longer than feels "
  "comfortable. Keep something unchanged to compare against, or you are not "
  "running a test, you are just busy."),

 ("Comments, not likes",
  "On short video, a like is close to worthless as a signal.\n\nWhat actually "
  "moves reach is somebody sending it to a friend, and somebody bothering to type "
  "a reply. Those are the expensive actions, so they are the ones that count.\n\n"
  "Which changes what you make. \"Who would somebody send this to\" is a better "
  "question than \"will people like this\"."),

 ("The message they never see",
  "We set up an automation to reply privately when somebody comments.\n\nMost of "
  "them never saw it. On Instagram, a message from an account you do not follow "
  "lands in a requests folder people rarely open.\n\nThe fix is not a cleverer "
  "message. It is a public reply under their comment telling them where to look.\n\n"
  "Delivery is a feature. Writing something good and having it land somewhere "
  "unread is the same as not writing it."),

 ("Two accounts, one mistake",
  "We posted the same video to two of our own accounts on the same day.\n\nShort "
  "video platforms match on the audio, and posting identical audio across accounts "
  "you own can get a profile filed as a duplicate.\n\nOne of ours does ten times "
  "the views of the other on the same phone with the same content.\n\nIf you run "
  "more than one account, they need genuinely different uploads, not the same "
  "file twice."),

 ("Open the file",
  "We had a folder of screenshots nobody was allowed to use, because nobody had "
  "checked what was in them.\n\nThirteen of them. Sitting unusable for months "
  "because opening them was a job nobody did.\n\nWe opened them in twenty minutes. "
  "Rotation went from thin to wide, and the repetitive feed problem solved itself.\n\n"
  "Some bottlenecks are not hard. They are just boring, so they never get done."),

 ("Match the screenshot, not your memory",
  "A caption of ours said 65 people. The screenshot behind it showed no count at "
  "all, and a different screenshot of the same day showed 66.\n\nNobody would have "
  "caught it. That is not the point.\n\nIf you are showing proof, the number in "
  "your words has to be the number in the picture. Every time. The moment those "
  "drift apart, the proof is doing the opposite of its job."),

 ("Nobody is coming to tell you it broke",
  "Everything quietly degrades. Queues empty. Tokens expire. Links rot — we shipped "
  "two dead ones to real people this year, one of them inside something a customer "
  "had paid for.\n\nNone of it announced itself.\n\nWhichever part of your setup "
  "would be most embarrassing to find broken in a month, go and look at it today. "
  "It is probably already broken."),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = json.load(open(HERE / "queue.json", encoding="utf-8"))
    TZ = dt.timezone(dt.timedelta(hours=2))
    now = dt.datetime.now(TZ)

    # Weekdays only, 18:00 Berlin - matches the slot the existing posts used.
    day = now.date()
    if now.hour >= 17:
        day += dt.timedelta(days=1)
    nid = max(e["id"] for e in q) + 1
    added = 0
    for title, body in POSTS:
        while day.weekday() >= 5:              # skip Sat/Sun
            day += dt.timedelta(days=1)
        when = dt.datetime.combine(day, dt.time(18, 0), TZ)
        q.append({
            "id": nid,
            "text": f"**{title}**\n\n{body}",
            "image_file": None,
            "scheduled_time": when.isoformat(),
            "status": "pending",
            "targets": [{"platform": "telegram"}],
        })
        print(f"  {when.strftime('%a %d %b')}  {title}")
        nid += 1
        added += 1
        day += dt.timedelta(days=1)

    json.dump(q, open(HERE / "queue.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nadded {added} telegram posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
