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
MAX_DASHBOARD_PER = 3         # window size for the dashboard-spam check
MAX_DASHBOARD_IN_WINDOW = 2   # 2 different dashboards side by side is fine; 3 in a
                              # row is what made the feed look like one screenshot
                              # with the number swapped (the original complaint).
MAX_CONSECUTIVE_IMAGES = 3  # 4 image + 2 text per day
MAX_CHARS = 490               # Threads limit; other platforms differ (see limit_for)
PLATFORM_MAX_CHARS = {        # per-platform caps, checked against an entry's targets
    "threads": 490,
    "facebook": 5000,
    "telegram": 4096,         # 1024 when a photo is attached
    "telegram_photo": 1024,
    "x": 280,
}
MAX_EMOJI = 2

# Engagement bait — every one of these formats measurably flopped (0-2 likes).
BAIT_PATTERNS = [
    r"\bdrop a\b", r"\bdrop an?\b.{0,12}\bemoji\b", r"\btag someone\b", r"\bfight me\b",
    r"\bcomment\b.{0,20}\bbelow\b", r"\bwrong answers only\b", r"\brate your\b",
    r"\bfinish the sentence\b", r"\bwhat'?s your first move\b", r"\bwho'?s with me\b",
    r"\bunpopular opinion\b", r"\bam i wrong\b", r"\bthoughts\?\s*$",
]

# Still banned outright: black heart, ghost, pleading face, star-eyes, fire,
# money bag, money-mouth. These read as hype and nothing using them performed.
BANNED_EMOJI = ["\U0001f5a4", "\U0001f47b", "\U0001f979",
                "\U0001f929", "\U0001f525", "\U0001f4b0", "\U0001f911"]

# 😭 and 💸 came OFF the ban list 2026-08-11. The blanket ban was wrong on the
# evidence: the two highest-reach posts this account has ever had (26,423 and
# 13,019 views) both used the pair. But they only work as an occasional
# exclamation - on every post they are exactly the hype-spam the reset was
# about. So: rate-limited, not banned. Shawn's rule is "once in a while, and
# only when you think the post will go viral", which means the big-swing posts.
HYPE_EMOJI = {"\U0001f62d", "\U0001f4b8"}      # 😭 💸
HYPE_EVERY = 8          # at most one hype post per 8 upcoming posts, per account

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
    return re.findall(r"\$\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\$\d+(?:\.\d{1,2})?", text or "")


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

    upcoming = [e for e in queue if e.get("status") in ("pending", "held")]
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

    # ---- hype emoji spacing (per account) ----
    # Allowed, but rationed. Spam is what killed them last time, not the glyphs.
    for account in ("MAIN", "TDS"):
        acct = [e for e in upcoming if account in accounts_of(e)]
        last_hype = None
        for i, entry in enumerate(acct):
            text = body(entry)
            if not any(g in text for g in HYPE_EMOJI):
                continue
            if last_hype is not None and (i - last_hype) < HYPE_EVERY:
                flag(entry, f"hype emoji used {i - last_hype} posts after the last one "
                            f"— keep at least {HYPE_EVERY} apart")
            last_hype = i

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
            if len(entries) > 2:
                for e in entries[2:]:
                    flag(e, f"more than 2 'rare' big-number images in {month} — keep them occasional")

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
