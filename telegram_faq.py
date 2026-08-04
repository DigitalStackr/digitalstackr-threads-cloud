"""
Telegram DM auto-responder.

Runs inside the same GitHub Actions tick as the scheduler, so there is no server
and no webhook. It polls getUpdates, answers direct messages that match a small
FAQ, and stays silent-but-helpful on anything it doesn't recognise.

DESIGN RULES (deliberate, do not "improve" these away):
  * Every reply is clearly FROM THE BOT. It never writes in Shawn's voice or
    implies a human is typing.
  * It NEVER guesses. If the message doesn't match the FAQ confidently, it hands
    off to a human instead of inventing an answer.
  * Every number it states is a real, approved figure (prices only). It quotes no
    earnings, no results, no income claims — those belong in posts with a
    screenshot attached, never in a DM where nothing backs them up.
  * It answers each user's message exactly once (offset is persisted), so a
    stuck queue can't spam anyone.

Offset persistence: telegram_offset.json in the repo. Telegram deletes an update
once you request a higher offset, so committing the offset is what stops a replay
after a re-run.

Env vars:
  TELEGRAM_BOT_TOKEN — BotFather token
  TELEGRAM_OWNER     — handle to hand off to, e.g. "@digitalstackr"
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

API = "https://api.telegram.org"
OFFSET_PATH = Path(__file__).parent / "telegram_offset.json"

GUMROAD = "https://digitalstackr.gumroad.com"
LINKS = {
    "fde":  GUMROAD + "/l/faceless-digital-empire",
    "trl":  GUMROAD + "/l/threads-hunter-blueprint",
    "ment": GUMROAD + "/l/mentorship",
    "dfy":  GUMROAD + "/l/doneforyou-business",
}

# Each entry: (name, [keyword patterns], answer).
# Answers are plain, honest, and price-accurate. No earnings claims anywhere.
FAQ = [
    (
        "what_is_fde",
        [r"\bwhat is\b.*\bfde\b", r"\bfaceless digital empire\b", r"\bwhat.*(product|fde).*about\b",
         r"\bwhat do you sell\b", r"\bwhat's fde\b", r"\bwhats fde\b"],
        "<b>Faceless Digital Empire (FDE)</b> is a digital guide on building a faceless "
        "online brand and selling a digital product — picking what to make, building it, "
        "setting up Gumroad, and posting consistently.\n\n"
        "It's a one-time purchase, no subscription.",
    ),
    (
        "price",
        [r"\bhow much\b", r"\bprice\b", r"\bcost\b", r"\bpricing\b", r"\bhow much is\b"],
        "Current prices:\n\n"
        "• <b>Faceless Digital Empire</b> — $27\n"
        "• <b>Threads Revenue Ladder</b> — $9\n"
        "• <b>1-on-1 mentorship</b> — $97\n"
        "• <b>Done-For-You setup</b> — $147\n\n"
        "All one-time payments.",
    ),
    (
        "where_buy",
        [r"\bwhere\b.*\bbuy\b", r"\bhow.*\b(buy|purchase|get it|order)\b", r"\blink\b",
         r"\bcheckout\b", r"\bwhere can i\b"],
        "Direct links:\n\n"
        f"• <b>Faceless Digital Empire</b> ($27)\n{LINKS['fde']}\n\n"
        f"• <b>Threads Revenue Ladder</b> ($9)\n{LINKS['trl']}\n\n"
        f"• <b>Mentorship</b> ($97)\n{LINKS['ment']}\n\n"
        f"• <b>Done-For-You</b> ($147)\n{LINKS['dfy']}\n\n"
        "Pay and the file downloads straight away.",
    ),
    (
        "is_it_legit",
        [r"\bis this (legit|real|a scam|fake)\b", r"\bscam\b", r"\blegit\b", r"\breal\b.*\?",
         r"\btrust\b", r"\bproof\b"],
        "Fair question — you should ask it.\n\n"
        "Everything is sold through <b>Gumroad</b>, which handles payment and refunds, so "
        "you're not sending money to a stranger directly. The screenshots posted are real "
        "and unedited.\n\n"
        "If a product isn't what you expected, you can request a refund through Gumroad.",
    ),
    (
        "refund",
        [r"\brefund\b", r"\bmoney back\b", r"\bguarantee\b", r"\bcancel\b"],
        "Refunds are handled by <b>Gumroad</b>, not by us directly — use the refund option "
        "on your Gumroad receipt email and it goes through their system.",
    ),
    (
        "beginner",
        [r"\bbeginner\b", r"\bnew to this\b", r"\bno experience\b", r"\bjust start(ed|ing)\b",
         r"\bwork for me\b", r"\bcomplete beginner\b"],
        "It's written for beginners — it assumes you're starting with no audience and no "
        "product.\n\n"
        "It won't do the work for you though. You still have to build the thing and post "
        "consistently.",
    ),
    (
        "what_is_dfy",
        [r"\bdone.?for.?you\b", r"\bdfy\b", r"\bdo it for me\b", r"\bset.?up for me\b"],
        "<b>Done-For-You ($147)</b> is where the store gets built for you — the product, "
        "the store copy, the pricing, and a delivery page.\n\n"
        f"You still run the account and post.\n{LINKS['dfy']}",
    ),
]

FALLBACK = (
    "I'm an automated bot, so I only know a few things and I don't want to guess "
    "and get it wrong.\n\nFor anything else, message {owner} directly and you'll get "
    "a proper answer."
)

GREETING = (
    "Hey — I'm the DigitalStackr bot. 🤍\n\n"
    "I can answer a few common questions:\n"
    "• what FDE is\n"
    "• prices\n"
    "• where to buy\n"
    "• refunds\n\n"
    "Just ask. For anything else I'll point you to a human."
)


def _token():
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not t:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    return t


def _load_offset() -> int:
    if OFFSET_PATH.exists():
        try:
            return int(json.loads(OFFSET_PATH.read_text(encoding="utf-8")).get("offset", 0))
        except Exception:
            return 0
    return 0


def _save_offset(offset: int) -> None:
    OFFSET_PATH.write_text(json.dumps({"offset": offset}, indent=2) + "\n", encoding="utf-8")


def match_faq(text: str):
    """Return an answer, or None if nothing matches confidently."""
    low = (text or "").lower().strip()
    if not low:
        return None
    if low in ("/start", "start", "hi", "hey", "hello") or low.startswith("/start"):
        return GREETING
    for _name, patterns, answer in FAQ:
        for p in patterns:
            if re.search(p, low):
                return answer
    return None


def reply(token: str, chat_id: int, text: str) -> None:
    requests.post(f"{API}/bot{token}/sendMessage",
                  data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                        "disable_web_page_preview": "true"},
                  timeout=30)


def main() -> int:
    token = _token()
    owner = os.environ.get("TELEGRAM_OWNER", "@digitalstackr")
    offset = _load_offset()

    r = requests.get(f"{API}/bot{token}/getUpdates",
                     params={"offset": offset, "timeout": 0, "allowed_updates": '["message"]'},
                     timeout=45)
    data = r.json()
    if not data.get("ok"):
        print(f"telegram getUpdates failed: {data.get('description')}", flush=True)
        return 1

    updates = data.get("result", [])
    if not updates:
        print("telegram: no new DMs", flush=True)
        return 0

    answered = handed_off = 0
    highest = offset
    for u in updates:
        highest = max(highest, u["update_id"] + 1)
        msg = u.get("message") or {}
        chat = msg.get("chat") or {}
        # Only answer private DMs. Channel posts and groups are ignored on purpose.
        if chat.get("type") != "private":
            continue
        text = msg.get("text") or ""
        answer = match_faq(text)
        if answer:
            reply(token, chat["id"], answer)
            answered += 1
        else:
            reply(token, chat["id"], FALLBACK.format(owner=owner))
            handed_off += 1

    # Confirm server-side straight away: calling getUpdates with the higher offset
    # makes Telegram drop those updates for good. Belt and braces alongside the
    # committed offset file — if the commit is ever lost, we still don't re-answer
    # someone who already got a reply.
    try:
        requests.get(f"{API}/bot{token}/getUpdates",
                     params={"offset": highest, "timeout": 0}, timeout=30)
    except Exception as e:
        print(f"telegram: offset confirm failed ({e}) — file offset still saved", flush=True)

    _save_offset(highest)
    print(f"telegram: {answered} answered, {handed_off} handed off, offset -> {highest}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
