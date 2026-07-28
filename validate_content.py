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
IMAGE_REUSE_DAYS = 7
MAX_DASHBOARD_PER = 3         # at most 1 dashboard in every 3 image posts
MAX_CONSECUTIVE_IMAGES = 2
MAX_CHARS = 490
MAX_EMOJI = 2

# Engagement bait — every one of these formats measurably flopped (0-2 likes).
BAIT_PATTERNS = [
    r"\bdrop a\b", r"\bdrop an?\b.{0,12}\bemoji\b", r"\btag someone\b", r"\bfight me\b",
    r"\bcomment\b.{0,20}\bbelow\b", r"\bwrong answers only\b", r"\brate your\b",
    r"\bfinish the sentence\b", r"\bwhat'?s your first move\b", r"\bwho'?s with me\b",
    r"\bunpopular opinion\b", r"\bam i wrong\b", r"\bthoughts\?\s*$",
]

# Only the white heart is on-brand.
BANNED_EMOJI = ["\U0001f5a4", "\U0001f4b8", "\U0001f62d", "\U0001f47b", "\U0001f979",
                "\U0001f929", "\U0001f525", "\U0001f4b0", "\U0001f911"]

# The ONLY figures that may appear in a caption without a screenshot backing them.
# Anything else must be present in the attached image's manifest 'numbers'.
ALLOWED_STANDALONE_FIGURES = {"$382", "$27", "$19", "$97", "$147", "$9", "$0", "$200"}


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
    return re.findall(r"\$[0-9][0-9,]*(?:\.[0-9]{1,2})?", text or "")


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
        text = entry.get("text", "") or ""
        img = entry.get("image_file")

        if len(text) > MAX_CHARS:
            flag(entry, f"caption {len(text)} chars > {MAX_CHARS}")

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

        caps = [w for w in re.findall(r"\b[A-Z]{2,}\b", text)
                if w not in {"AM", "PM", "PDF", "LLC", "DM", "US", "OK", "ID"}]
        if len(caps) > 1:
            flag(entry, f"{len(caps)} ALL-CAPS phrases > 1 ({caps})")

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
            if not meta.get("usable", False):
                flag(entry, f"image '{img}' blocked: {meta.get('blocked_reason')}")
            allowed = set(meta.get("numbers", []))
            for fig in figures:
                if fig not in allowed and fig not in ALLOWED_STANDALONE_FIGURES:
                    flag(entry, f"caption cites {fig} but image shows {sorted(allowed)}")
        else:
            for fig in figures:
                if fig not in ALLOWED_STANDALONE_FIGURES:
                    flag(entry, f"text-only post cites unbacked figure {fig}")

    # ---- dedupe against history AND within the batch ----
    history = [(e.get("id"), e.get("text", "")) for e in recent_posted]
    seen = []
    for entry in upcoming:
        text = entry.get("text", "")
        for pid, ptext in history:
            if similarity(text, ptext) >= NEAR_DUP_THRESHOLD:
                flag(entry, f"duplicate/near-duplicate of already-posted id{pid}")
                break
        for sid, stext in seen:
            if similarity(text, stext) >= NEAR_DUP_THRESHOLD:
                flag(entry, f"duplicate/near-duplicate of queued id{sid}")
                break
        seen.append((entry.get("id"), text))

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
                if window.count("dashboard") > 1:
                    flag(entry, f"more than 1 dashboard in the last {MAX_DASHBOARD_PER} image posts")
            else:
                run = 0

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
