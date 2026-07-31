"""
Media stock report — how much runway is left before we run out of screenshots or reels.

Answers the question Shawn actually asks: "when do the reels run out and when do
I need to make more?" Run it any time:

    python media_inventory.py

Reports, per folder:
  * how many files exist
  * how many are VERIFIED (safe to post) vs unverified (blocked)
  * which are unused, and which are getting over-used
  * how many days of runway remain at the current posting rate
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
QUEUE = HERE / "queue.json"

# folder -> (manifest file, posts/day that consume it)
FOLDERS = {
    "images": ("image_manifest.json", 8),        # 4 image posts/day x 2 accounts
    "novina_images": ("novina_manifest.json", 2),  # ~2 image posts/day
    "reels": (None, 0),                          # consumed by IG/TikTok when scheduled
}
VIDEO_EXT = (".mp4", ".mov")
IMAGE_EXT = (".png", ".jpg", ".jpeg")


def load_queue():
    if not QUEUE.exists():
        return []
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def verified_set(manifest_name):
    if not manifest_name:
        return None
    p = HERE / manifest_name
    if not p.exists():
        return set()
    m = json.loads(p.read_text(encoding="utf-8"))
    return {k for k, v in m.get("verified", {}).items() if v.get("tier") != "blocked"}


def main():
    queue = load_queue()
    now = datetime.now(timezone.utc)

    # how often each media file is already scheduled/used
    used = Counter()
    upcoming = Counter()
    for e in queue:
        for key in ("image_file", "video_file"):
            f = e.get(key)
            if not f:
                continue
            used[f] += 1
            try:
                if datetime.fromisoformat(e["scheduled_time"]) > now and \
                        e.get("status") in ("pending", "partial", "held"):
                    upcoming[f] += 1
            except Exception:
                pass

    print("MEDIA INVENTORY\n" + "=" * 60)
    for folder, (manifest, per_day) in FOLDERS.items():
        d = HERE / folder
        if not d.exists():
            print(f"\n{folder}/  — folder not present locally (check the repo)")
            continue

        exts = VIDEO_EXT if folder == "reels" else IMAGE_EXT
        files = sorted(f.name for f in d.iterdir() if f.suffix.lower() in exts)
        ok = verified_set(manifest)

        print(f"\n{folder}/  — {len(files)} file(s)")
        if ok is not None:
            usable = [f for f in files if f in ok]
            blocked = [f for f in files if f not in ok]
            print(f"  verified & usable : {len(usable)}")
            print(f"  NOT verified      : {len(blocked)}  (blocked until opened + recorded)")
            if blocked:
                for b in blocked[:6]:
                    print(f"      - {b}")
                if len(blocked) > 6:
                    print(f"      ... and {len(blocked)-6} more")
        else:
            usable = files

        never = [f for f in usable if used[f] == 0]
        if never:
            print(f"  never used yet    : {len(never)}")
            for n in never[:8]:
                print(f"      + {n}")

        if per_day and usable:
            # with a 2-day reuse rule each file supports ~1 post every 2 days
            capacity_per_day = len(usable) / 2
            days = capacity_per_day / per_day * 2 if per_day else 0
            verdict = "OK" if len(usable) >= per_day * 2 else "LOW — send more"
            print(f"  burn rate         : ~{per_day} post(s)/day")
            print(f"  status            : {verdict}")

        if folder == "reels":
            if not usable:
                print("  >>> NO REELS. Instagram + TikTok cannot post until you upload some.")
            else:
                heavy = [(f, used[f]) for f in usable if used[f] >= 3]
                if heavy:
                    print("  over-used (3+ times) — time for fresh ones:")
                    for f, c in heavy:
                        print(f"      ! {f}  used {c}x")
                sched = sum(upcoming[f] for f in usable)
                print(f"  scheduled ahead   : {sched} post(s)")

    print("\n" + "=" * 60)
    print("Upload: github.com -> open the folder -> Add file -> Upload files -> Commit.")
    print("Then tell Claude, so each new file gets opened, verified and recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
