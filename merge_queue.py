"""
Semantic 3-way-ish merge for queue.json.

WHY THIS EXISTS
---------------
Two scheduler runs can overlap (GitHub's native cron and the cron-job.org
workflow_dispatch both fire at the top of the hour, seconds apart; the
concurrency group does not reliably serialize them). Both runs then commit
queue.json, and `git rebase` hits a CONFLICT it can never auto-resolve — the
retry loop repeats the same conflict 5x and the run fails (failure emails), while
the queue update is lost so the next tick can re-fire an already-sent post.

git cannot merge this file: it's one JSON blob mutated in many places. But the
data has a natural conflict-free merge rule, which this implements.

MERGE RULES (in priority order)
-------------------------------
1. A 'posted' target result ALWAYS wins over anything else, from either side.
   This is the safety-critical rule: never lose the record that something was
   published, because losing it is what causes a double-post.
2. Entry status is recomputed from the merged per-target results, so it can
   never disagree with them.
3. attempts = max(ours, theirs)  — retry budget is never silently reset.
4. For entries with nothing posted yet, keep the LATER scheduled_time, so a
   self-heal reschedule is never undone into an immediate re-fire.
5. Entries present on only one side are kept as-is (covers queue_add.py adding
   new posts while the scheduler is mid-run).

Usage:  python merge_queue.py OURS.json THEIRS.json OUT.json
"""
import json
import sys

from scheduler import get_targets, target_key

POSTED = "posted"


def _merge_results(a: dict, b: dict) -> dict:
    """Union of per-target results; a 'posted' record always wins."""
    out = dict(a or {})
    for key, res in (b or {}).items():
        cur = out.get(key)
        if cur is None:
            out[key] = res
            continue
        if cur.get("status") == POSTED:
            continue                      # never overwrite a posted record
        if res.get("status") == POSTED:
            out[key] = res                # promote to posted
        # else: both non-posted — keep whichever we already had
    return out


def _recompute_status(entry: dict) -> str:
    """Derive entry status from merged results so the two can't disagree."""
    targets = get_targets(entry)
    results = entry.get("results") or {}
    statuses = [results.get(target_key(t), {}).get("status", "failed") for t in targets]
    if all(s == POSTED for s in statuses):
        return POSTED
    if any(s == POSTED for s in statuses):
        return "partial"
    return entry.get("status", "pending")


def merge_entry(ours: dict, theirs: dict) -> dict:
    merged = dict(theirs)                  # start from origin's view
    merged.update({k: v for k, v in ours.items()
                   if k not in ("results", "status", "scheduled_time", "attempts")})

    results = _merge_results(ours.get("results"), theirs.get("results"))
    # Don't invent an empty results{} on legacy entries that never had one — that
    # would rewrite hundreds of untouched historical entries on every merge and
    # bury the real change in noise.
    if results or "results" in ours or "results" in theirs:
        merged["results"] = results
    else:
        merged.pop("results", None)

    merged["attempts"] = max(int(ours.get("attempts", 0)), int(theirs.get("attempts", 0)))
    if not merged["attempts"]:
        merged.pop("attempts", None)

    new_status = _recompute_status(merged)
    # 'expired' is terminal — only honour it if neither side posted anything.
    if POSTED not in [r.get("status") for r in results.values()]:
        if "expired" in (ours.get("status"), theirs.get("status")):
            new_status = "expired"
        else:
            # keep the later scheduled_time so a self-heal push-forward survives
            times = [t for t in (ours.get("scheduled_time"), theirs.get("scheduled_time")) if t]
            if times:
                merged["scheduled_time"] = max(times)
    merged["status"] = new_status

    for field in ("posted_at", "thread_id"):
        if field in ours and field not in merged:
            merged[field] = ours[field]
    return merged


def merge_queues(ours: list, theirs: list) -> list:
    ours_by_id = {e["id"]: e for e in ours}
    theirs_by_id = {e["id"]: e for e in theirs}

    out, seen = [], set()
    for entry in theirs:                    # origin order is the canonical order
        eid = entry["id"]
        seen.add(eid)
        out.append(merge_entry(ours_by_id[eid], entry) if eid in ours_by_id else entry)
    for entry in ours:                      # entries only we know about
        if entry["id"] not in seen:
            out.append(entry)
    return out


def main() -> int:
    ours_path, theirs_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(ours_path, encoding="utf-8") as f:
        ours = json.load(f)
    with open(theirs_path, encoding="utf-8") as f:
        theirs = json.load(f)

    merged = merge_queues(ours, theirs)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
        f.write("\n")

    posted = sum(1 for e in merged if e.get("status") == POSTED)
    print(f"merged queue: {len(merged)} entries ({posted} posted) "
          f"from ours={len(ours)} theirs={len(theirs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
