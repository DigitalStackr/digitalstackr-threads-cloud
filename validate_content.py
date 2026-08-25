"""
Content rule enforcement for the DigitalStackr queue (content reset 2026-07-28).

This exists because three bugs shipped to the live feed:
  1. The same caption posted TWICE ("small accounts can't sell", "get experience first").
  2. ~90% of image posts reused the same Gumroad dashboard with a different number,
     which lets followers add the numbers up and catch inconsistencies.
  3. Captions cited figures that weren't in the attached screenshot.

Nothing queues unless it passes every check here. Run:
    python validate_content.py queue.json
Exit code 0 = clean, 1 = violations found (they are printed).
"""
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
MANIFEST_PATH = HERE / "image_manifest.json"

# --- rules ---------------------------------------------------------------
DEDUPE_LOOKBACK = 60          # compare against the last 60 posted, both accounts
NEAR_DUP_THRESHOLD = 0.82     # token overlap above this = too similar
IMAGE_REUSE_DAYS = 2        # relaxed 2026-07-30: reuse is fine, just never back-to-back
# 'rare' = the big-number screenshots. Was 2 per month, which suppressed the
# best-performing asset on the account: '3.9k gumroad ss.png' ($3,937.55) medians
# 3,870 views and produced the 26,426 and 23,803 posts. Big numbers are not the
# risk the old rule assumed - they are what travels. 8/account/month keeps them
# from becoming the ONLY thing posted without rationing them into uselessness.
# Raised again 8 -> 24 on 2026-08-25. The 400-post pull is unambiguous: TWO OF
# THE TOP THREE POSTS EVER use $3,937, and the winners run $3,937 / $3,898 /
# $1,183 / $1,109 / $856 against $382 / $17.16 / $50 for the flops. Big numbers
# are not the credibility risk the original rule assumed - they are the format.
# What still protects the feed is the image REUSE window below, which stops the
# same screenshot appearing twice in a week. That is the real anti-monotony rule;
# this one was a proxy for it and was throttling the strategy.
RARE_PER_MONTH = 24

MAX_DASHBOARD_PER = 3         # window size for the dashboard-spam check
MAX_DASHBOARD_IN_WINDOW = 3   # widened from 2 on 2026-08-23 to fit 8 posts/day;
# still the real guard against feed monotony. 3 different dashboards side by side is fine; 4 in a
                              # row is what made the feed look like one screenshot
                              # with the number swapped (the original complaint).
MAX_CONSECUTIVE_IMAGES = 999  # effectively OFF as of 2026-08-23.
# Images median 327 views against 189 for text across 400 measured posts. The
# strategy is now images ONLY, so a rule capping consecutive images was directly
# blocking the better-performing format. Feed monotony is handled by the DASHBOARD
# window below, which is the check that actually addresses "same Gumroad screen,
# different number" - the complaint this rule was mistakenly written for.
MAX_CHARS = 490               # Threads limit; other platforms differ (see limit_for)
PLATFORM_MAX_CHARS = {        # per-platform caps, checked against an entry's targets
    "threads": 490,
    "facebook": 5000,
    "telegram": 4096,         # 1024 when a photo is attached
    "telegram_photo": 1024,
    # X Premium raises the ceiling from 280 to 25,000. Capped at 4,000 here
    # because that is the useful limit for a readable long-form post, not the
    # technical one. Short Threads captions were being recycled onto X, which
    # is the wrong format for the platform entirely.
    "x": 4000,
}
MAX_EMOJI = 5   # was 2. The 27,867-view post used 3 (💸🏦🥹) and would have failed.

# Engagement bait — every one of these formats measurably flopped (0-2 likes).
BAIT_PATTERNS = [
    r"\bdrop a\b", r"\bdrop an?\b.{0,12}\bemoji\b", r"\btag someone\b", r"\bfight me\b",
    r"\bcomment\b.{0,20}\bbelow\b", r"\bwrong answers only\b", r"\brate your\b",
    r"\bfinish the sentence\b", r"\bwhat'?s your first move\b", r"\bwho'?s with me\b",
    r"\bunpopular opinion\b", r"\bam i wrong\b", r"\bthoughts\?\s*$",
]

# Still banned outright: black heart, ghost, star-eyes, fire, money bag,
# money-mouth. These read as hype and nothing using them performed.
BANNED_EMOJI = []   # emptied 2026-08-23 - see EMOJI/CAPS note below

# 😭 and 💸 came OFF the ban list 2026-08-11. The blanket ban was wrong on the
# evidence: the two highest-reach posts this account has ever had (26,423 and
# 13,019 views) both used the pair. But they only work as an occasional
# exclamation - on every post they are exactly the hype-spam the reset was
# about. So: rate-limited, not banned. Shawn's rule is "once in a while, and
# only when you think the post will go viral", which means the big-swing posts.
# 🥹 joined them 2026-08-13 on the same evidence: two of the five best posts in
# the last 30 days use it, and those two took the most FOLLOWS of any post on the
# account (54 and 50). It reads as genuine emotion on a milestone, which is the
# one place hype is earned.
HYPE_EMOJI = {"\U0001f62d", "\U0001f4b8", "\U0001f979"}      # 😭 💸 🥹
HYPE_EVERY = 6          # at most one hype post per 6 upcoming posts, per account

# The ONLY figures that may appear in a caption without a screenshot backing them.
# Anything else must be present in the attached image's manifest 'numbers'.
# Current prices only. $19 (old TRL) and $50 (old mentorship) are deliberately NOT
# here: they are still valid on a post whose screenshot shows that historical sale,
# but a text-only post must never quote them as if they were the price today.
ALLOWED_STANDALONE_FIGURES = {"$382", "$27", "$9", "$97", "$147", "$0", "$200"}

# Platforms that publish the caption WITHOUT the entry's image, so a money figure
# there has no screenshot behind it. X came OFF this list on 2026-08-05 when media
# upload shipped. Instagram is Reels-only and carries no screenshots at all.
# Add a platform here the moment its media path is unavailable, not after.
MEDIA_LESS_PLATFORMS = {"instagram"}


# Every product URL that is allowed to appear in an auto-plug, pulled from the
# Gumroad API on 2026-08-20 and confirmed against a live request. This list is a
# scar: two dead links have already shipped to real people - the whole
# focusfilesstudio.gumroad.com domain after the handle change, and the invented
# slug "threads-revenue-ladder" (the real one is threads-hunter-blueprint), which
# went out inside a paying client's delivery page. A plug is nothing BUT a link,
# so a wrong one makes the entire reply worthless.
# Adding a URL here without opening it first defeats the point.
KNOWN_PRODUCT_URLS = {
    "https://digitalstackr.gumroad.com/l/faceless-digital-empire",
    "https://digitalstackr.gumroad.com/l/threads-hunter-blueprint",
    "https://digitalstackr.gumroad.com/l/mentorship",
    "https://digitalstackr.gumroad.com/l/doneforyou-business",
    "https://digitalstackr.gumroad.com/l/threads-algo-boss-kit",
    "https://digitalstackr.gumroad.com/l/50-product-ideas",
    "https://digitalstackr.gumroad.com/l/lazyprofittracker",
}

# ---------------------------------------------------------------------------
# CAPS + EMOJI BANS REMOVED 2026-08-23, on measured evidence.
#
# The rules said: one ALL-CAPS phrase max, no full caps on TDS, hype emoji
# (😭💸🥹) rationed to one per six posts, and a banned-emoji list.
#
# Then 400 posts were pulled from the Threads API with per-post insights. The
# top of that list:
#
#   27,867  "IT'S OFFICIAL!!!!! 💸 Payout just landed: $3,898.40 🏦 ... 🥹"
#   19,215  "ITS FINALLY OFFICIAL!!!!! I can finally say it..."
#    8,772  "This is passive income 🥹"
#    3,879  "DONT STOP ENGAGING ON THREADSSSS!!!! ... $1.8K OF MY DEBT 🥳🎉"  (TDS)
#
# Every one of those would have been rejected or flagged by the rules above, and
# the TDS example directly contradicts "full caps die on TDS". The rules were
# written from a bad read; the account's own data says loud, excited, emoji-heavy
# celebration is its best-performing register.
#
# WHAT IS DELIBERATELY KEPT, and must not be relaxed:
#   - every $ figure in a caption must appear in the attached screenshot
#   - dedupe against history and within the batch
#   - images must exist and be manifest-verified
#   - platform length caps (over-length posts fail at the API, not here)
#   - the auto_plug URL allowlist (two dead links have shipped to real people)
#
# Tone is a preference. Those five are correctness.
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", (text or "").lower())
    return re.sub(r"[^a-z0-9$ ]+", " ", text)


def _tokens(text: str) -> set:
    return {t for t in _norm(text).split() if len(t) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def count_emoji(text: str) -> int:
    return sum(1 for ch in (text or "")
               if unicodedata.category(ch) == "So" or ord(ch) > 0x1F000)


def money_figures(text: str) -> list:
    # Proper money shape only. The looser [0-9,]* version swallowed a trailing
    # comma ("$27," in prose) and then failed to match the manifest's "$27".
    #
    # The comma-grouped alternative MUST come first, and the un-grouped one must
    # allow any digit count: the earlier \d{1,3}(?:,\d{3})* pattern matched only
    # the first three digits of an un-grouped figure, so "$1638.53" was read as
    # "$163" and then reported as not matching its own screenshot.
    #
    # EUR added 2026-08-19: the Stripe screenshots are in euros, and a €-figure
    # was sailing past this check completely unvalidated. Any currency symbol we
    # actually post in has to be matched here or the whole figure/image rule has
    # a hole in it.
    return re.findall(
        r"[$€]\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|[$€]\d+(?:\.\d{1,2})?",
        text or "")


def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate(queue: list) -> list:
    """Return a list of human-readable violations. Empty list = clean."""
    manifest = load_manifest()
    verified = manifest["verified"]
    unverified = set(manifest["unverified_do_not_use"])
    problems = []

    posted = [e for e in queue if e.get("status") == "posted"]
    posted.sort(key=lambda e: e.get("scheduled_time", ""))
    recent_posted = posted[-DEDUPE_LOOKBACK:]

    # "held" is EXCLUDED on purpose. scheduler.py only fires "pending", so a held
    # entry never publishes - counting it in the spacing/dedupe checks lets content
    # that will never go out constrain content that will. Found 2026-08-23 after 52
    # plain receipts were held: the single hype-emoji post left in the queue was
    # flagged for sitting too close to a held one nobody would ever see.
    # A revived entry goes back to "pending" and is validated then.
    upcoming = [e for e in queue if e.get("status") == "pending"]
    upcoming.sort(key=lambda e: e.get("scheduled_time", ""))

    def flag(entry, msg):
        problems.append(f"id{entry.get('id','?')} [{entry.get('account','?')}] {msg}")

    # ---- per-entry checks ----
    for entry in upcoming:
        # A long-form thread carries its words in thread_parts, not text. Without
        # this the validator would wave a whole thread through unread - no dedupe,
        # no bait check, no figure check on any part after the hook.
        parts = entry.get("thread_parts")
        text = "\n".join(parts) if parts else (entry.get("text", "") or "")
        img = entry.get("image_file")

        if parts:
            if len(parts) > 12:
                flag(entry, f"thread has {len(parts)} parts, max 12")
            for i, p in enumerate(parts, 1):
                if len(p) > MAX_CHARS:
                    flag(entry, f"thread part {i} is {len(p)} chars > {MAX_CHARS}")
                if not p.strip():
                    flag(entry, f"thread part {i} is empty")

        # Char limit is per-platform: a Telegram essay is fine, the same text
        # would be rejected by Threads and truncated by X.
        targets = entry.get("targets") or [{"platform": "threads"}]
        for t in targets:
            plat = t.get("platform", "threads")
            # Threads entries are length-checked per part above; the joined text is
            # meant to exceed a single post's limit, that's the point of a thread.
            if parts and plat == "threads":
                continue
            key = "telegram_photo" if (plat == "telegram" and img) else plat
            cap = PLATFORM_MAX_CHARS.get(key, MAX_CHARS)
            if len(text) > cap:
                flag(entry, f"caption {len(text)} chars > {cap} for {plat}")

        for pat in BAIT_PATTERNS:
            if re.search(pat, text, re.I):
                flag(entry, f"engagement bait matched /{pat}/")
                break

        if text.rstrip().endswith("?"):
            flag(entry, "ends in a question — rules require declarative statements")

        for e in BANNED_EMOJI:
            if e in text:
                flag(entry, f"banned emoji {e!r} (white heart only)")
                break

        n_emoji = count_emoji(text)
        if n_emoji > MAX_EMOJI:
            flag(entry, f"{n_emoji} emoji > {MAX_EMOJI}")

        # ALL-CAPS cap removed 2026-08-05 (Shawn's call). The winning long-form
        # thread format opens on a full-caps declarative hook — every top post in
        # the July report does — so the old "1 caps phrase max" rule blocked the
        # format we're moving to. Earlier measurement that full caps died on TDS
        # is superseded: TDS now mirrors MAIN so the two can be compared directly.

        # Every target is judged against the media IT will actually carry, not
        # against the entry as a whole. 15 X posts shipped bare dollar figures
        # because the entry looked fine - image_file was set, but only Threads
        # sent it. A per-target variant text is also invisible to the entry-level
        # check below, so it is validated here.
        for t in targets:
            plat = t.get("platform", "threads")
            ttext = t.get("text") if t.get("text") is not None else text
            timg = (t.get("image_file") or entry.get("image_file")) \
                if plat not in MEDIA_LESS_PLATFORMS else None
            for fig in money_figures(ttext):
                if fig in ALLOWED_STANDALONE_FIGURES:
                    continue
                if not timg:
                    flag(entry, f"{plat} target cites {fig} with no image attached "
                                f"- unbacked income claim")
                elif fig not in set(verified.get(timg, {}).get("numbers", [])):
                    flag(entry, f"{plat} target cites {fig} but its image {timg!r} "
                                f"shows {sorted(verified.get(timg, {}).get('numbers', []))}")

        # number / image matching
        figures = money_figures(text)
        if img:
            if img in unverified:
                flag(entry, f"image '{img}' is UNVERIFIED — contents unknown, cannot be used")
                continue
            meta = verified.get(img)
            if not meta:
                flag(entry, f"image '{img}' missing from manifest")
                continue
            if meta.get("tier") == "blocked":
                flag(entry, f"image '{img}' blocked: {meta.get('blocked_reason')}")
            allowed = set(meta.get("numbers", []))
            for fig in figures:
                if fig not in allowed and fig not in ALLOWED_STANDALONE_FIGURES:
                    flag(entry, f"caption cites {fig} but image shows {sorted(allowed)}")
        else:
            for fig in figures:
                if fig not in ALLOWED_STANDALONE_FIGURES:
                    flag(entry, f"text-only post cites unbacked figure {fig}")

    # ---- dedupe against history AND within the batch, PER ACCOUNT ----
    # Scoped to the account on purpose: the rule protects a reader from seeing the
    # same post twice in one feed. MAIN and TDS deliberately run the same content
    # so the two audiences can be compared, and a cross-account match is that
    # design working, not a fault.
    def accounts_of(e):
        accts = {t.get("account") for t in (e.get("targets") or [])
                 if t.get("platform", "threads") == "threads" and t.get("account")}
        return accts or {e.get("account") or "MAIN"}

    def body(e):
        return "\n".join(e["thread_parts"]) if e.get("thread_parts") else e.get("text", "")

    seen = []
    for entry in upcoming:
        text = body(entry)
        mine = accounts_of(entry)
        for pid, ptext, pacct in [(e.get("id"), body(e), accounts_of(e)) for e in recent_posted]:
            if (mine & pacct) and similarity(text, ptext) >= NEAR_DUP_THRESHOLD:
                flag(entry, f"duplicate/near-duplicate of already-posted id{pid}")
                break
        for sid, stext, sacct in seen:
            if (mine & sacct) and similarity(text, stext) >= NEAR_DUP_THRESHOLD:
                flag(entry, f"duplicate/near-duplicate of queued id{sid}")
                break
        seen.append((entry.get("id"), text, mine))


    # ---- image reuse window + dashboard ratio + consecutive images (per account) ----
    for account in ("MAIN", "TDS"):
        acct = [e for e in upcoming if e.get("account") == account]
        last_used = {}
        # seed from history so we don't reuse something just posted
        for e in recent_posted:
            if e.get("account") == account and e.get("image_file"):
                try:
                    last_used[e["image_file"]] = datetime.fromisoformat(e["scheduled_time"])
                except Exception:
                    pass

        run = 0
        window = []
        for entry in acct:
            img = entry.get("image_file")
            try:
                when = datetime.fromisoformat(entry["scheduled_time"])
            except Exception:
                continue

            if img:
                run += 1
                if run > MAX_CONSECUTIVE_IMAGES:
                    flag(entry, f"{run} image posts in a row > {MAX_CONSECUTIVE_IMAGES}")
                prev = last_used.get(img)
                if prev and abs((when - prev).days) < IMAGE_REUSE_DAYS:
                    flag(entry, f"image '{img}' reused within {IMAGE_REUSE_DAYS} days")
                last_used[img] = when

                kind = verified.get(img, {}).get("kind", "unknown")
                window.append(kind)
                if len(window) > MAX_DASHBOARD_PER:
                    window.pop(0)
                if window.count("dashboard") > MAX_DASHBOARD_IN_WINDOW:
                    flag(entry, f"{window.count(chr(34)+chr(34)) or window.count('dashboard')} dashboards "
                                f"in the last {MAX_DASHBOARD_PER} image posts — reads as spam")
            else:
                run = 0

    # ---- 'rare' (big-number) images: at most once per calendar month, per account ----
    # Shawn's rule: the large historical figures may appear about once a month, never
    # as a routine post, because stacking them invites followers to add them up.
    for account in ("MAIN", "TDS"):
        by_month = {}
        for entry in [e for e in upcoming if e.get("account") == account]:
            img = entry.get("image_file")
            if not img or verified.get(img, {}).get("tier") != "rare":
                continue
            month = str(entry.get("scheduled_time", ""))[:7]
            by_month.setdefault(month, []).append(entry)
        for month, entries in by_month.items():
            if len(entries) > RARE_PER_MONTH:
                for e in entries[RARE_PER_MONTH:]:
                    flag(e, f"more than {RARE_PER_MONTH} 'rare' big-number images in {month} — keep them occasional")

    # ---- auto-plug CTAs ----
    # A plug is a REAL publish to Threads - a reply under our own post - but it
    # used to bypass every check in this file, because it lives in entry["auto_plug"]
    # rather than entry["text"]. So a plug could carry a banned emoji, run over the
    # character cap, quote a figure with no screenshot behind it, or point at a dead
    # URL, and nothing here would notice. It is held to the same bar as a post.
    for entry in upcoming:
        plug = entry.get("auto_plug")
        if not plug or plug.get("status") != "pending":
            continue
        ptext = plug.get("text") or ""

        if not ptext.strip():
            flag(entry, "auto_plug has no text")
            continue
        if len(ptext) > PLATFORM_MAX_CHARS["threads"]:
            flag(entry, f"auto_plug is {len(ptext)} chars; threads max "
                        f"{PLATFORM_MAX_CHARS['threads']}")

        urls = re.findall(r"https?://\S+", ptext)
        if not urls:
            flag(entry, "auto_plug has no link - a CTA with no destination is noise")
        for u in urls:
            if u.rstrip(".,)") not in KNOWN_PRODUCT_URLS:
                flag(entry, f"auto_plug points at an unrecognised URL {u} - "
                            f"verify it resolves, then add it to KNOWN_PRODUCT_URLS")

        for emo in BANNED_EMOJI:
            if emo in ptext:
                flag(entry, f"auto_plug contains banned emoji {emo}")

        # A plug is a reply. It carries NO image of its own, so any figure in it is
        # unbacked by definition - same rule as a text-only post.
        for fig in money_figures(ptext):
            if fig not in ALLOWED_STANDALONE_FIGURES:
                flag(entry, f"auto_plug cites unbacked figure {fig} - a reply has no "
                            f"screenshot attached")

        # Check the PROSE, not the whole string: a plug always ends with its URL,
        # so testing the raw text for a trailing "?" can never fire. Caught by a
        # negative test: a plug reading "want the system?" then the URL on the
        # next line sailed straight through the raw-text version of this check.
        prose = re.sub(r"https?://\S+", "", ptext).strip()
        if prose.endswith("?"):
            flag(entry, "auto_plug ends on a question - measured failure")

    return problems


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "queue.json")
    with open(path, encoding="utf-8") as f:
        queue = json.load(f)
    problems = validate(queue)
    if not problems:
        print(f"CONTENT OK — no violations in {path}")
        return 0
    print(f"CONTENT VIOLATIONS ({len(problems)}) in {path}:")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())
