"""Local test harness for the multi-platform scheduler. Mocks all posters — no real API calls."""
import json, tempfile, os, sys
from datetime import datetime, timezone, timedelta

import scheduler

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS  {name}")
    else: FAIL += 1; print(f"  FAIL  {name}")

def iso(dt): return dt.isoformat()

# ---- mock posters ----
calls = []
def fake_text(account, text): calls.append(("text", account, text)); return f"th_{account}_{len(calls)}"
def fake_image(account, text, img): calls.append(("image", account, img)); return f"th_{account}_img_{len(calls)}"
def fake_fb(text, image_url=None): calls.append(("fb", image_url)); return "fb_ok_1"
def fake_fb_fail(text, image_url=None): raise RuntimeError("FB boom")

def run_tick(queue_list):
    """Point scheduler at a temp queue, run one tick, return the mutated queue."""
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(queue_list, tf); tf.close()
    lf = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8"); lf.close()
    scheduler.QUEUE_PATH = __import__("pathlib").Path(tf.name)
    scheduler.LOG_PATH = __import__("pathlib").Path(lf.name)
    scheduler.main()
    with open(tf.name, encoding="utf-8") as f:
        return json.load(f)

def by_id(q, i): return next(e for e in q if e["id"] == i)

now = datetime.now(timezone.utc)

# =====================================================================
# TEST 1 — backward compat against the REAL queue.json (no firing, structure only)
# =====================================================================
print("\n[TEST 1] Backward compat: real queue.json entries all map to valid Threads targets")
with open("queue.json", encoding="utf-8") as f:
    real = json.load(f)
pend = [e for e in real if e.get("status") == "pending"]
ok = True
for e in real:
    tg = scheduler.get_targets(e)
    if not tg: ok = False; print("   empty targets:", e.get("id")); break
    for t in tg:
        if t.get("platform", "threads") == "threads" and t.get("account") not in ("MAIN", "TDS"):
            ok = False; print("   bad account on", e.get("id"), t); break
check(f"all {len(real)} real entries yield valid targets (legacy path intact)", ok)
check("real queue has pending entries to protect", len(pend) > 0)

# =====================================================================
# TEST 2 — firing: legacy + multi-target + variants + expiry + future-skip
# =====================================================================
print("\n[TEST 2] Firing behavior")
scheduler.post_text = fake_text
scheduler.post_image = fake_image
scheduler.post_facebook = fake_fb
scheduler.MAX_POSTS_PER_TICK = 100  # fire everything for the test
calls.clear()

q = [
  {"id":1,"account":"MAIN","text":"legacy main","scheduled_time":iso(now),"status":"pending"},
  {"id":2,"account":"TDS","text":"legacy img","image_file":"foo.png","scheduled_time":iso(now),"status":"pending"},
  {"id":3,"account":"MAIN","text":"future","scheduled_time":iso(now+timedelta(hours=5)),"status":"pending"},
  {"id":4,"account":"MAIN","text":"old","scheduled_time":iso(now-timedelta(hours=5)),"status":"pending"},
  {"id":5,"text":"multi","image_file":"bar.png","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"}]},
  {"id":6,"text":"fb only","scheduled_time":iso(now),"status":"pending","targets":[{"platform":"facebook"}]},
  {"id":7,"text":"shared","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN","text":"main variant"},
              {"platform":"threads","account":"TDS","text":"tds variant"}]},
]
q = run_tick(q)

check("id1 legacy text -> posted", by_id(q,1)["status"]=="posted")
check("id1 recorded threads:MAIN result", by_id(q,1)["results"]["threads:MAIN"]["status"]=="posted")
check("id1 legacy thread_id mirrored", "thread_id" in by_id(q,1))
check("id2 legacy image -> posted via post_image", by_id(q,2)["status"]=="posted" and ("image","TDS","foo.png") in calls)
check("id3 future entry left pending", by_id(q,3)["status"]=="pending")
check("id4 old entry expired", by_id(q,4)["status"]=="expired")
check("id5 multi -> posted (both platforms)", by_id(q,5)["status"]=="posted")
check("id5 threads:MAIN + facebook both posted",
      by_id(q,5)["results"]["threads:MAIN"]["status"]=="posted" and by_id(q,5)["results"]["facebook"]["status"]=="posted")
check("id5 facebook got raw github url for image",
      ("fb", scheduler.raw_image_url("bar.png")) in calls)
check("id6 facebook-only -> posted", by_id(q,6)["status"]=="posted")
check("id7 per-target variants both sent",
      ("text","MAIN","main variant") in calls and ("text","TDS","tds variant") in calls)

# =====================================================================
# TEST 3 — failure ISOLATION + retry without double-post
# =====================================================================
print("\n[TEST 3] Isolation + retry")
scheduler.post_facebook = fake_fb_fail   # facebook now fails
calls.clear()
q2 = [
  {"id":10,"text":"iso test","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"}]},
]
q2 = run_tick(q2)
check("id10 threads posted despite FB failing (isolation)",
      by_id(q2,10)["results"]["threads:MAIN"]["status"]=="posted")
check("id10 facebook recorded failed", by_id(q2,10)["results"]["facebook"]["status"]=="failed")
check("id10 overall status = partial", by_id(q2,10)["status"]=="partial")

# next tick: FB recovers. Threads must NOT be re-sent; FB now posts.
threads_calls_before = sum(1 for c in calls if c[0]=="text")
scheduler.post_facebook = fake_fb
q2 = run_tick(q2)
threads_calls_after = sum(1 for c in calls if c[0]=="text")
check("id10 threads NOT re-sent on retry (no double-post)", threads_calls_after == threads_calls_before)
check("id10 facebook posted on retry", by_id(q2,10)["results"]["facebook"]["status"]=="posted")
check("id10 overall now posted", by_id(q2,10)["status"]=="posted")

# =====================================================================
# TEST 4 — unimplemented platform (x) isolated as failed, doesn't crash
# =====================================================================
print("\n[TEST 4] Unimplemented platform is isolated, not fatal")
calls.clear()
q3 = [
  {"id":20,"text":"x not ready","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"x"}]},
]
q3 = run_tick(q3)
check("id20 threads still posted", by_id(q3,20)["results"]["threads:MAIN"]["status"]=="posted")
check("id20 x failed cleanly (not implemented)", by_id(q3,20)["results"]["x"]["status"]=="failed")
check("id20 overall partial", by_id(q3,20)["status"]=="partial")

print(f"\n==== RESULT: {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
