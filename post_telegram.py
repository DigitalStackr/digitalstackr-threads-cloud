"""
Telegram channel posting via the Bot API.

Simplest integration of the lot: no OAuth, no token refresh, no audit gate. The
bot token is long-lived and the bot is an administrator of the channel with
can_post_messages, so a single HTTP call publishes.

Env vars (from repo secrets):
  TELEGRAM_BOT_TOKEN  — the BotFather token
  TELEGRAM_CHANNEL    — "@digitalstackr" (or the numeric -100... id)

Text  -> POST /sendMessage  (chat_id, text)
Photo -> POST /sendPhoto    (chat_id, photo=<public url>, caption)

Images are passed by PUBLIC URL (raw.githubusercontent.com), exactly like
Facebook and Instagram — Telegram fetches it server-side, no upload needed. That
keeps the "real screenshots only, from the repo" rule intact.

FORMATTING: Telegram accepts HTML in text/caption. We use parse_mode=HTML and
only <b> and <i>, because anything richer is noise on a phone. Any literal
<, > or & in the caption is escaped first so a stray character can't break the
message or silently drop it.

RATE LIMIT: Telegram allows roughly 1 message/second to the same chat (and ~20
messages/minute to a channel). Our volume is a couple of posts a week, so this
never binds — but MIN_INTERVAL_SEC below enforces spacing anyway in case we ever
burst-send a backfill.
"""
import html
import os
import re
import time

import requests

API = "https://api.telegram.org"

# Telegram's documented limits. Captions are much shorter than message bodies.
MAX_TEXT = 4096
MAX_CAPTION = 1024

# Guard against burst-sending. ~1 msg/sec to the same chat is the documented cap.
MIN_INTERVAL_SEC = 1.1
_last_send = {"t": 0.0}


def _creds():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL environment variable")
    return token, channel


def _throttle():
    wait = MIN_INTERVAL_SEC - (time.time() - _last_send["t"])
    if wait > 0:
        time.sleep(wait)
    _last_send["t"] = time.time()


def to_html(text: str) -> str:
    """Escape the caption, then re-enable a deliberately tiny markup subset.

    Authors write **bold** and _italic_ in the queue (same as everywhere else);
    everything else is escaped so a stray '<' or '&' can't break the send.
    """
    safe = html.escape(text or "", quote=False)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe, flags=re.S)
    safe = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<i>\1</i>", safe, flags=re.S)
    return safe


def _call(token: str, method: str, payload: dict) -> dict:
    _throttle()
    r = requests.post(f"{API}/bot{token}/{method}", data=payload, timeout=60)
    try:
        data = r.json()
    except ValueError:
        r.raise_for_status()
        raise RuntimeError(f"Telegram returned non-JSON (status {r.status_code})")
    if not data.get("ok"):
        # 429 carries retry_after; surface it so the scheduler's self-heal can back off.
        retry = (data.get("parameters") or {}).get("retry_after")
        extra = f" (retry_after={retry}s)" if retry else ""
        raise RuntimeError(f"Telegram API error {data.get('error_code')}: "
                           f"{data.get('description')}{extra}")
    return data["result"]


def post_telegram(text: str, image_url: str = None) -> str:
    """Publish to the channel. Returns the message id as a string."""
    token, channel = _creds()
    body = to_html(text)

    if image_url:
        if len(body) > MAX_CAPTION:
            raise RuntimeError(f"Telegram caption is {len(body)} chars; max {MAX_CAPTION} "
                               f"when a photo is attached")
        result = _call(token, "sendPhoto", {
            "chat_id": channel, "photo": image_url,
            "caption": body, "parse_mode": "HTML",
        })
    else:
        if len(body) > MAX_TEXT:
            raise RuntimeError(f"Telegram message is {len(body)} chars; max {MAX_TEXT}")
        result = _call(token, "sendMessage", {
            "chat_id": channel, "text": body, "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        })

    return str(result.get("message_id"))


def delete_telegram(message_id: str) -> bool:
    """Remove a message (used to clean up test posts)."""
    token, channel = _creds()
    try:
        _call(token, "deleteMessage", {"chat_id": channel, "message_id": message_id})
        return True
    except RuntimeError:
        return False
