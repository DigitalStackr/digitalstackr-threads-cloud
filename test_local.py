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
def fake_image(account, text, img, image_dir="images"): calls.append(("image", account, img, image_dir)); return f"th_{account}_img_{len(calls)}"
def fake_fb(text, image_url=None): calls.append(("fb", image_url)); return "fb_ok_1"
def fake_fb_fail(text, image_url=None): raise RuntimeError("FB boom")
def fake_ig(text, image_url=None, video_url=None, carousel_urls=None, share_to_feed=True):
    calls.append(("ig", video_url or image_url or tuple(carousel_urls or ()))); return "ig_ok_1"
def fake_ig_fail(text, **kw): raise RuntimeError("IG boom")

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
check("id2 legacy image -> posted via post_image", by_id(q,2)["status"]=="posted" and ("image","TDS","foo.png","images") in calls)
check("id3 future entry left pending", by_id(q,3)["status"]=="pending")
# Self-heal: an overdue post is no longer silently dropped — it's rescheduled forward.
check("id4 overdue entry rescheduled, not expired",
      by_id(q,4)["status"]=="pending" and by_id(q,4).get("attempts")==1)
check("id4 pushed to a future time",
      datetime.fromisoformat(by_id(q,4)["scheduled_time"]) > now)
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

# =====================================================================
# TEST 5 — self-healing: failed posts auto-reschedule; exhausted ones expire
# =====================================================================
print("\n[TEST 5] Self-healing reschedule")
scheduler.post_text = fake_text
scheduler.post_image = fake_image
scheduler.post_facebook = fake_fb_fail   # facebook fails -> a facebook-only entry fully fails
scheduler.MAX_POSTS_PER_TICK = 100
calls.clear()

# 5a: an entry whose only target fails is rescheduled forward (not left dead)
q5 = [{"id":40,"text":"fb only fails","scheduled_time":iso(now),"status":"pending",
       "targets":[{"platform":"facebook"}]}]
q5 = run_tick(q5)
check("id40 fully-failed entry set back to pending (self-heal)", by_id(q5,40)["status"]=="pending")
check("id40 attempts incremented to 1", by_id(q5,40).get("attempts")==1)
check("id40 rescheduled into the future", datetime.fromisoformat(by_id(q5,40)["scheduled_time"]) > now)

# 5b: an overdue entry that already exhausted its retries finally expires
q5b = [{"id":41,"text":"done retrying","scheduled_time":iso(now-timedelta(hours=5)),
        "status":"pending","attempts":scheduler.MAX_RETRIES}]
q5b = run_tick(q5b)
check("id41 expires only after MAX_RETRIES exhausted", by_id(q5b,41)["status"]=="expired")

# 5c: a partial entry (some targets posted) is NOT double-posted on its retry tick
scheduler.post_facebook = fake_fb_fail
calls.clear()
q5c = [{"id":42,"text":"partial","scheduled_time":iso(now),"status":"pending",
        "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"}]}]
q5c = run_tick(q5c)
check("id42 goes partial (threads ok, fb fail)", by_id(q5c,42)["status"]=="partial")
threads_before = sum(1 for c in calls if c[0]=="text")
scheduler.post_facebook = fake_fb           # fb recovers
q5c = run_tick(q5c)
threads_after = sum(1 for c in calls if c[0]=="text")
check("id42 threads NOT re-sent on partial retry (no double-post)", threads_after==threads_before)
check("id42 now fully posted after fb recovers", by_id(q5c,42)["status"]=="posted")

# =====================================================================
# TEST 6 — Instagram: reels / image / carousel + media-required + isolation
# =====================================================================
print("\n[TEST 6] Instagram")
scheduler.post_text = fake_text
scheduler.post_image = fake_image
scheduler.post_facebook = fake_fb
scheduler.post_instagram = fake_ig
scheduler.MAX_POSTS_PER_TICK = 100
calls.clear()

q6 = [
  {"id":50,"text":"reel caption","video_file":"hook1.mp4","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"instagram"}]},
  {"id":51,"text":"ig photo","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"instagram"}]},
  {"id":52,"text":"ig carousel","carousel":["a.png","b.png","c.mp4"],"scheduled_time":iso(now),
   "status":"pending","targets":[{"platform":"instagram"}]},
  {"id":53,"text":"no media","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"instagram"}]},
  # Fan-out: the SAME entry carries a screenshot for threads/fb AND a reel for IG.
  {"id":54,"text":"fan out","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"},
              {"platform":"instagram","video_file":"hook2.mp4"}]},
]
q6 = run_tick(q6)

check("id50 reel posted via video_url from reels/ folder",
      by_id(q6,50)["status"]=="posted" and ("ig", scheduler.raw_video_url("hook1.mp4")) in calls)
# REELS-ONLY POLICY: images and carousels must be refused before hitting the API.
check("id51 ig IMAGE target refused (reels-only policy)",
      by_id(q6,51)["results"]["instagram"]["status"]=="failed"
      and "reels-only" in by_id(q6,51)["results"]["instagram"]["error"].lower())
check("id51 no image was ever sent to IG",
      not any(c[0]=="ig" and c[1]==scheduler.raw_image_url("foo.png") for c in calls))
check("id52 ig CAROUSEL target refused (reels-only policy)",
      by_id(q6,52)["results"]["instagram"]["status"]=="failed"
      and "reels-only" in by_id(q6,52)["results"]["instagram"]["error"].lower())
check("id53 text-only IG target refused with clear reason",
      by_id(q6,53)["results"]["instagram"]["status"]=="failed"
      and "video_file" in by_id(q6,53)["results"]["instagram"]["error"])
check("id53 self-heal bounces it to pending for retry (never publishes)",
      by_id(q6,53)["status"]=="pending" and by_id(q6,53).get("attempts")==1)
check("id54 fan-out: screenshot to threads/fb, reel to IG, all posted",
      by_id(q6,54)["status"]=="posted")
check("id54 IG got the REEL url, not the screenshot",
      ("ig", scheduler.raw_video_url("hook2.mp4")) in calls
      and ("fb", scheduler.raw_image_url("foo.png")) in calls)
check("id54 all three platforms recorded",
      {"threads:MAIN","facebook","instagram"} <= set(by_id(q6,54)["results"].keys()))

# isolation: IG failing must not stop threads/facebook
scheduler.post_instagram = fake_ig_fail
calls.clear()
q6b = [{"id":55,"text":"iso","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
        "targets":[{"platform":"threads","account":"MAIN"},
                   {"platform":"instagram","video_file":"hook3.mp4"}]}]
q6b = run_tick(q6b)
check("id55 threads posted despite IG failing (isolation)",
      by_id(q6b,55)["results"]["threads:MAIN"]["status"]=="posted")
check("id55 overall partial, IG marked failed",
      by_id(q6b,55)["status"]=="partial" and by_id(q6b,55)["results"]["instagram"]["status"]=="failed")

# self-heal + no double-post carries over to IG
threads_before = sum(1 for c in calls if c[0]=="text")
scheduler.post_instagram = fake_ig
q6b = run_tick(q6b)
threads_after = sum(1 for c in calls if c[0]=="text")
check("id55 threads NOT re-sent when IG retries (no double-post)", threads_after==threads_before)
check("id55 fully posted once IG recovers", by_id(q6b,55)["status"]=="posted")

# =====================================================================
# TEST 7 — queue.json semantic merge (concurrent scheduler runs)
# =====================================================================
print("\n[TEST 7] Concurrent-run queue merge")
import merge_queue

# The real-world race: two runs fire the SAME entry's different targets, or one
# run posts and the other still thinks it's pending. Merging must never lose a
# 'posted' record (that's what causes double-posts).
ours = [
  {"id":60,"text":"a","scheduled_time":iso(now),"status":"partial",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"}],
   "results":{"threads:MAIN":{"status":"posted","id":"th_1","at":"t1"},
              "facebook":{"status":"failed","error":"boom"}}},
  {"id":61,"text":"b","scheduled_time":iso(now),"status":"pending","account":"MAIN"},
  {"id":63,"text":"only ours (queue_add)","scheduled_time":iso(now),"status":"pending","account":"TDS"},
]
theirs = [
  {"id":60,"text":"a","scheduled_time":iso(now),"status":"partial",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"}],
   "results":{"threads:MAIN":{"status":"failed","error":"stale"},
              "facebook":{"status":"posted","id":"fb_1","at":"t2"}}},
  {"id":61,"text":"b","scheduled_time":iso(now),"status":"posted","account":"MAIN",
   "results":{"threads:MAIN":{"status":"posted","id":"th_2","at":"t3"}}},
  {"id":62,"text":"only theirs","scheduled_time":iso(now),"status":"pending","account":"MAIN"},
]
m = merge_queue.merge_queues(ours, theirs)
mb = {e["id"]: e for e in m}

check("merge keeps BOTH posted records for id60 (no publish lost)",
      mb[60]["results"]["threads:MAIN"]["status"]=="posted"
      and mb[60]["results"]["facebook"]["status"]=="posted")
check("merge upgrades id60 to fully posted", mb[60]["status"]=="posted")
check("merge never downgrades a posted entry (id61 stays posted)",
      mb[61]["status"]=="posted" and mb[61]["results"]["threads:MAIN"]["id"]=="th_2")
check("merge keeps entries only origin had (id62)", 62 in mb)
check("merge keeps entries only we had (id63, queue_add race)", 63 in mb)
check("merge preserves total entry count", len(m)==4)

# self-heal interaction: a reschedule must not be undone by the merge
later = (now + timedelta(minutes=20)).isoformat()
o2 = [{"id":70,"text":"x","scheduled_time":later,"status":"pending","account":"MAIN","attempts":2}]
t2 = [{"id":70,"text":"x","scheduled_time":iso(now),"status":"pending","account":"MAIN","attempts":1}]
m2 = {e["id"]: e for e in merge_queue.merge_queues(o2, t2)}
check("merge keeps the LATER scheduled_time (self-heal survives)",
      m2[70]["scheduled_time"]==later)
check("merge keeps the HIGHER attempts count", m2[70]["attempts"]==2)

# a posted entry must never be resurrected to pending by a stale peer
o3 = [{"id":71,"text":"y","scheduled_time":iso(now),"status":"pending","account":"MAIN"}]
t3 = [{"id":71,"text":"y","scheduled_time":iso(now),"status":"posted","account":"MAIN",
       "results":{"threads:MAIN":{"status":"posted","id":"th_9","at":"t"}}}]
m3 = {e["id"]: e for e in merge_queue.merge_queues(o3, t3)}
check("stale 'pending' cannot un-post a published entry (no double-post)",
      m3[71]["status"]=="posted")

# =====================================================================
# TEST 8 — TikTok routing (audit-gated; uploads local bytes, not a URL)
# =====================================================================
print("\n[TEST 8] TikTok")
def fake_tt(text, video_path, privacy_level=None, disable_comment=False):
    calls.append(("tt", video_path, privacy_level)); return "tt_pub_1"
def fake_tt_fail(text, video_path, **kw): raise RuntimeError("TT boom")

scheduler.post_tiktok = fake_tt
scheduler.post_instagram = fake_ig
scheduler.MAX_POSTS_PER_TICK = 100
calls.clear()

q8 = [
  {"id":80,"text":"tt reel","video_file":"hook1.mp4","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"tiktok"}]},
  {"id":81,"text":"tt no media","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"tiktok"}]},
  {"id":82,"text":"tt carousel","carousel":["a.png","b.png"],"scheduled_time":iso(now),
   "status":"pending","targets":[{"platform":"tiktok"}]},
  {"id":83,"text":"privacy override","video_file":"hook1.mp4","scheduled_time":iso(now),
   "status":"pending","targets":[{"platform":"tiktok","privacy_level":"SELF_ONLY"}]},
  {"id":84,"text":"all platforms","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"},
              {"platform":"instagram","video_file":"r.mp4"},{"platform":"tiktok","video_file":"r.mp4"}]},
]
q8 = run_tick(q8)

check("id80 tiktok posts from a LOCAL reels/ path (not a url)",
      by_id(q8,80)["status"]=="posted"
      and any(c[0]=="tt" and str(c[1]).endswith("hook1.mp4") and "http" not in str(c[1]) for c in calls))
check("id81 tiktok without video refused",
      by_id(q8,81)["results"]["tiktok"]["status"]=="failed"
      and "video_file" in by_id(q8,81)["results"]["tiktok"]["error"])
check("id82 tiktok carousel refused (needs verified domain)",
      by_id(q8,82)["results"]["tiktok"]["status"]=="failed"
      and "verified domain" in by_id(q8,82)["results"]["tiktok"]["error"])
check("id83 per-target privacy_level passed through",
      any(c[0]=="tt" and c[2]=="SELF_ONLY" for c in calls))
check("id84 one entry fans out to all four platforms",
      by_id(q8,84)["status"]=="posted"
      and {"threads:MAIN","facebook","instagram","tiktok"} <= set(by_id(q8,84)["results"].keys()))

# isolation: TikTok failing must not affect the other three
scheduler.post_tiktok = fake_tt_fail
calls.clear()
q8b = [{"id":85,"text":"iso","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
        "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"},
                   {"platform":"tiktok","video_file":"r.mp4"}]}]
q8b = run_tick(q8b)
check("id85 threads+fb posted despite TikTok failing (isolation)",
      by_id(q8b,85)["results"]["threads:MAIN"]["status"]=="posted"
      and by_id(q8b,85)["results"]["facebook"]["status"]=="posted")
check("id85 overall partial with tiktok failed",
      by_id(q8b,85)["status"]=="partial" and by_id(q8b,85)["results"]["tiktok"]["status"]=="failed")

# =====================================================================
# TEST 9 — Telegram routing + formatting + FAQ bot
# =====================================================================
print("\n[TEST 9] Telegram")
def fake_tg(text, image_url=None): calls.append(("tg", image_url, text)); return "msg_1"
def fake_tg_fail(text, image_url=None): raise RuntimeError("TG boom")

scheduler.post_telegram = fake_tg
scheduler.post_tiktok = fake_tt
scheduler.post_instagram = fake_ig
scheduler.MAX_POSTS_PER_TICK = 100
calls.clear()

q9 = [
  {"id":90,"text":"telegram text only","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"telegram"}]},
  {"id":91,"text":"telegram with shot","image_file":"foo.png","scheduled_time":iso(now),
   "status":"pending","targets":[{"platform":"telegram"}]},
  {"id":92,"text":"everywhere","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"facebook"},
              {"platform":"telegram"},{"platform":"instagram","video_file":"r.mp4"}]},
]
q9 = run_tick(q9)

check("id90 telegram text-only posts (unlike IG, no media needed)",
      by_id(q9,90)["status"]=="posted" and ("tg",None,"telegram text only") in calls)
check("id91 telegram photo uses the public images/ url",
      by_id(q9,91)["status"]=="posted"
      and any(c[0]=="tg" and c[1]==scheduler.raw_image_url("foo.png") for c in calls))
check("id92 one entry fans out to threads+fb+telegram+ig",
      by_id(q9,92)["status"]=="posted"
      and {"threads:MAIN","facebook","telegram","instagram"} <= set(by_id(q9,92)["results"].keys()))

# isolation + self-heal still hold for the new platform
scheduler.post_telegram = fake_tg_fail
calls.clear()
q9b = [{"id":93,"text":"iso","scheduled_time":iso(now),"status":"pending",
        "targets":[{"platform":"threads","account":"MAIN"},{"platform":"telegram"}]}]
q9b = run_tick(q9b)
check("id93 threads posted despite telegram failing (isolation)",
      by_id(q9b,93)["results"]["threads:MAIN"]["status"]=="posted")
threads_before = sum(1 for c in calls if c[0]=="text")
scheduler.post_telegram = fake_tg
q9b = run_tick(q9b)
threads_after = sum(1 for c in calls if c[0]=="text")
check("id93 threads NOT re-sent when telegram retries (no double-post)",
      threads_after==threads_before and by_id(q9b,93)["status"]=="posted")

# ---- HTML formatting: escape first, then allow only **bold** / _italic_ ----
import post_telegram as tg
check("telegram escapes raw HTML so a stray < can't break the send",
      tg.to_html("5 < 10 & rising") == "5 &lt; 10 &amp; rising")
check("telegram **bold** -> <b>", tg.to_html("**$382** this month") == "<b>$382</b> this month")
check("telegram _italic_ -> <i>", tg.to_html("_quietly_ building") == "<i>quietly</i> building")
check("telegram leaves snake_case words alone",
      tg.to_html("image_file stays intact") == "image_file stays intact")

# ---- FAQ bot: answers what it knows, refuses to guess otherwise ----
import telegram_faq as faq
check("FAQ answers 'how much'", "$27" in (faq.match_faq("how much is it?") or ""))
check("FAQ answers 'what is FDE'", "Faceless Digital Empire" in (faq.match_faq("what is FDE") or ""))
check("FAQ answers 'where do i buy'", "gumroad" in (faq.match_faq("where do i buy it") or "").lower())
check("FAQ answers 'is this legit'", "Gumroad" in (faq.match_faq("is this a scam?") or ""))
check("FAQ greets on /start", "bot" in (faq.match_faq("/start") or "").lower())
check("FAQ REFUSES to guess on an unknown question",
      faq.match_faq("can you build me a shopify store in france") is None)
check("FAQ fallback hands off to a human, makes no claim",
      "message" in faq.FALLBACK.lower() and "{owner}" in faq.FALLBACK)
# The bot must never state earnings in a DM - nothing backs it up there.
_allfaq = " ".join(a for _n,_p,a in faq.FAQ) + faq.FALLBACK + faq.GREETING
check("FAQ quotes prices only, never earnings",
      not any(t in _allfaq.lower() for t in ["/month","per month","a month","this month","today i made","income"]))

# =====================================================================
# TEST 10 — X: the URL cost guard ($0.015 vs $0.20 per post)
# =====================================================================
print("\n[TEST 10] X / Twitter URL cost guard")
import post_x as px

# --- URL detection: must catch every form X would auto-link and bill for ---
check("detects https:// url", px.extract_urls("grab it https://gum.co/fde now") != [])
check("detects bare www.", px.extract_urls("see www.digitalstackr.com") != [])
check("detects bare domain (X auto-links these too)",
      px.extract_urls("it's on digitalstackr.com today") != [])
check("detects gumroad link", px.extract_urls("digitalstackr.gumroad.com/l/fde") != [])
check("does NOT flag a plain money figure", px.extract_urls("$382 this month. 104 sales.") == [])
check("does NOT flag a decimal", px.extract_urls("made $181.30 today") == [])
check("does NOT flag a sentence end", px.extract_urls("one product. one platform.") == [])

# --- splitting: body must be clean, url preserved for the reply ---
body, urls = px.split_urls("built one product. get it at digitalstackr.com 🤍")
check("split removes the url from the body", "digitalstackr.com" not in body)
check("split keeps the url for the reply", urls and "digitalstackr.com" in urls[0])
check("split leaves no double spaces or dangling punctuation",
      "  " not in body and not body.endswith(" ."))
check("split leaves a url-free post completely untouched",
      px.split_urls("no links here at all") == ("no links here at all", []))

# --- cost model: the entire reason this module exists ---
check("url-free post bills at $0.015", abs(px.estimate_cost("plain post")-0.015) < 1e-9)
check("post WITH url still bills $0.015+$0.015 (not $0.20) because the link is a reply",
      abs(px.estimate_cost("go to digitalstackr.com")-0.030) < 1e-9)

# --- refuse mode ---
import os as _os
_os.environ["X_API_KEY"]="k"; _os.environ["X_API_SECRET"]="s"
_os.environ["X_ACCESS_TOKEN"]="t"; _os.environ["X_ACCESS_SECRET"]="ts"
_os.environ["X_URL_POLICY"]="refuse"
try:
    px.post_x("buy at digitalstackr.com")
    check("refuse mode blocks a url post", False)
except RuntimeError as e:
    check("refuse mode blocks a url post with a cost explanation",
          "0.20" in str(e) and "refuse" in str(e).lower())
_os.environ["X_URL_POLICY"]="reply"

# --- missing creds must name the Bearer-token trap explicitly ---
for k in ("X_API_KEY","X_API_SECRET","X_ACCESS_TOKEN","X_ACCESS_SECRET"):
    _os.environ.pop(k, None)
try:
    px.post_x("hello")
    check("missing creds raises", False)
except RuntimeError as e:
    check("missing creds explains Bearer token cannot post", "Bearer" in str(e))

# --- scheduler routing + isolation ---
def fake_x(text, image_url=None): calls.append(("x", text, image_url)); return "tweet_1"
def fake_x_fail(text, image_url=None): raise RuntimeError("X boom")
scheduler.post_x = fake_x
scheduler.post_telegram = fake_tg
scheduler.MAX_POSTS_PER_TICK = 100
calls.clear()
q10 = [
  {"id":100,"text":"one product. one platform.","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"x"}]},
  {"id":101,"text":"shared","image_file":"foo.png","scheduled_time":iso(now),"status":"pending",
   "targets":[{"platform":"threads","account":"MAIN"},{"platform":"telegram"},{"platform":"x"}]},
]
q10 = run_tick(q10)
check("id100 x posts", by_id(q10,100)["status"]=="posted" and ("x","one product. one platform.",None) in calls)
# id101 has image_file: X must now RECEIVE that screenshot, not silently drop it.
check("id101 x post carries the screenshot url",
      any(c[0]=="x" and c[2] and c[2].endswith("/images/foo.png") for c in calls))
check("id101 fans out to threads+telegram+x",
      {"threads:MAIN","telegram","x"} <= set(by_id(q10,101)["results"].keys()))

scheduler.post_x = fake_x_fail
calls.clear()
q10b = [{"id":102,"text":"iso","scheduled_time":iso(now),"status":"pending",
         "targets":[{"platform":"threads","account":"MAIN"},{"platform":"x"}]}]
q10b = run_tick(q10b)
check("id102 threads posted despite X failing (isolation)",
      by_id(q10b,102)["results"]["threads:MAIN"]["status"]=="posted")

# =====================================================================
print("\n[TEST 11] Long-form threads (reply chains)")
import post_thread as pt

chain = []
def fake_ptext(account, text, reply_to_id=None):
    chain.append((text, reply_to_id))
    return f"p{len(chain)}"
def fake_pimage(account, text, image_file, image_dir="images"):
    chain.append((text, f"IMG:{image_file}"))
    return f"p{len(chain)}"
pt.post_text, pt.post_image = fake_ptext, fake_pimage

chain.clear()
ids = pt.post_thread("MAIN", ["hook", "1. one", "2. two"], delay=0)
check("thread publishes every part", ids == ["p1", "p2", "p3"])
check("part 1 is a root (no parent)", chain[0][1] is None)
check("part 2 replies to part 1", chain[1][1] == "p1")
check("part 3 replies to part 2 (chain, not all-to-root)", chain[2][1] == "p2")

chain.clear()
pt.post_thread("MAIN", ["hook", "1. one"], image_file="foo.png", delay=0)
check("only the root carries the image", chain[0][1] == "IMG:foo.png" and chain[1][1] == "p1")

# Mid-thread failure must surface what already published, or the retry doubles part 1.
calls_n = {"n": 0}
def flaky(account, text, reply_to_id=None):
    calls_n["n"] += 1
    if calls_n["n"] == 3:
        raise RuntimeError("threads 500")
    return f"q{calls_n['n']}"
pt.post_text = flaky
try:
    pt.post_thread("MAIN", ["a", "b", "c", "d"], delay=0)
    check("partial thread raises", False)
except pt.ThreadPartialError as e:
    check("partial thread raises ThreadPartialError", True)
    check("partial thread reports the live parts", e.published == ["q1", "q2"])
    check("partial thread names the failing part", e.failed_index == 2)

# Resume: must NOT republish parts 1-2, and must re-parent onto part 2.
pt.post_text = fake_ptext
chain.clear()
ids2 = pt.post_thread("MAIN", ["a", "b", "c", "d"], published=["q1", "q2"], delay=0)
check("resume skips already-live parts", [c[0] for c in chain] == ["c", "d"])
check("resume re-parents onto the last live part", chain[0][1] == "q2")
check("resume returns the full id list", ids2[:2] == ["q1", "q2"] and len(ids2) == 4)
check("fully-published thread is a no-op",
      pt.post_thread("MAIN", ["a", "b"], published=["x1", "x2"], delay=0) == ["x1", "x2"])

# --- scheduler integration ---
scheduler.post_thread = pt.post_thread
q11 = [{"id": 200, "thread_parts": ["HOOK LINE", "1. first", "2. second"],
        "scheduled_time": iso(now), "status": "pending",
        "targets": [{"platform": "threads", "account": "MAIN"}]}]
chain.clear()
q11 = run_tick(q11)
r11 = by_id(q11, 200)["results"]["threads:MAIN"]
check("scheduler publishes a thread entry", by_id(q11, 200)["status"] == "posted")
check("scheduler stores every part id", len(r11.get("thread_ids", [])) == 3)
check("scheduler stores the ROOT as id (what the plug hangs off)",
      r11["id"] == r11["thread_ids"][0])

# =====================================================================
print("\n[TEST 12] Auto-plug (CTA only on posts that earned it)")
import auto_plug as ap
from datetime import datetime as _dt, timezone as _tz

stats_by_id, plugged = {}, []
ap.get_insights = lambda account, pid: stats_by_id.get(pid, {})
ap.post_text = lambda account, text, reply_to_id=None: (
    plugged.append((reply_to_id, text)) or f"plug{len(plugged)}")
NOW = _dt(2026, 8, 5, 12, 0, tzinfo=_tz.utc)

def plug_entry(eid, root, text="cta"):
    return {"id": eid, "status": "posted",
            "results": {"threads:MAIN": {"status": "posted", "id": root,
                                         "thread_ids": [root, root + "b"]}},
            "auto_plug": {"status": "pending", "account": "MAIN", "text": text}}

# Asserted against the CONSTANTS, not literals. These were hardcoded to 1499/1500
# and broke the moment the threshold was recalibrated on 2026-08-22 - and a test
# that has to be edited every time reach shifts is a test nobody trusts.
check("threshold: one below MIN_VIEWS does not qualify",
      not ap.qualifies({"views": ap.MIN_VIEWS - 1, "likes": 0}))
check("threshold: MIN_VIEWS qualifies",
      ap.qualifies({"views": ap.MIN_VIEWS, "likes": 0}))
check("threshold: MIN_LIKES qualifies on its own",
      ap.qualifies({"views": 10, "likes": ap.MIN_LIKES}))

plugged.clear()
# A real flop at current reach. 300 views used to be a flop against a 1,500 bar;
# after recalibration it CLEARS the bar, which is what broke this test.
stats_by_id = {"r1": {"views": max(1, ap.MIN_VIEWS // 3), "likes": ap.MIN_LIKES - 1}}
q12 = [plug_entry(300, "r1")]
ap.run(q12, now=NOW, log=lambda *a: None)
check("flop gets NO cta", plugged == [] and q12[0]["auto_plug"]["status"] == "pending")

plugged.clear()
stats_by_id = {"r2": {"views": 4000, "likes": 60}}
q12 = [plug_entry(301, "r2")]
changed = ap.run(q12, now=NOW, log=lambda *a: None)
check("winner gets a cta", len(plugged) == 1 and changed)
check("cta replies to the thread ROOT", plugged[0][0] == "r2")
check("plugged entry is marked posted", q12[0]["auto_plug"]["status"] == "posted")

plugged.clear()
ap.run(q12, now=NOW, log=lambda *a: None)
check("a plugged post is never plugged twice", plugged == [])

# Daily cap: three winners on one day still sell exactly once.
plugged.clear()
stats_by_id = {"a1": {"views": 9000}, "b1": {"views": 9000}, "c1": {"views": 9000}}
q12b = [plug_entry(310, "a1"), plug_entry(311, "b1"), plug_entry(312, "c1")]
ap.run(q12b, now=NOW, log=lambda *a: None)
check("daily cap holds: 3 winners -> 1 cta", len(plugged) == 1)
ap.run(q12b, now=NOW, log=lambda *a: None)
check("cap still holds on a later tick the same day", len(plugged) == 1)
tomorrow = _dt(2026, 8, 6, 12, 0, tzinfo=_tz.utc)
ap.run(q12b, now=tomorrow, log=lambda *a: None)
check("cap resets the next day", len(plugged) == 2)

# An unpublished / failed post must never be plugged.
plugged.clear()
q12c = [{"id": 320, "status": "failed",
         "results": {"threads:MAIN": {"status": "failed", "error": "boom"}},
         "auto_plug": {"status": "pending", "account": "MAIN", "text": "cta"}}]
ap.run(q12c, now=NOW, log=lambda *a: None)
check("failed post is never plugged", plugged == [])

# Insights outage must not crash the tick or fire a blind plug.
plugged.clear()
def boom(a, b): raise RuntimeError("insights down")
ap.get_insights = boom
q12d = [plug_entry(330, "r9")]
ap.run(q12d, now=NOW, log=lambda *a: None)
check("insights outage: no plug, no crash",
      plugged == [] and q12d[0]["auto_plug"]["status"] == "pending")


# ---- 13. auto_plug CTA text is validated like any other publish ----
# A plug is a real post to Threads - a reply under our own post - but it lived in
# entry["auto_plug"] rather than entry["text"], so every check in
# validate_content.py skipped it. A plug could carry a dead link, an unbacked
# figure, or a banned emoji straight to the live account.
#
# The URL allowlist matters most: a plug is nothing BUT a link, and two dead
# links have already shipped to real people (the focusfilesstudio domain after
# the handle change, and the invented slug "threads-revenue-ladder").
import validate_content as vcm

FDE_URL = "https://digitalstackr.gumroad.com/l/faceless-digital-empire"

def plug_problems(plug_text):
    entry = {"id": 9001, "account": "MAIN", "status": "pending",
             "text": "a plain text post with no figures",
             "scheduled_time": "2026-12-01T14:00:00+02:00",
             "targets": [{"platform": "threads", "account": "MAIN"}],
             "auto_plug": {"status": "pending", "account": "MAIN",
                           "text": plug_text}}
    return [p for p in vcm.validate([entry]) if "auto_plug" in p]

check("plug: dead domain is rejected",
      plug_problems("here it is\n\n"
                    "https://focusfilesstudio.gumroad.com/l/faceless-digital-empire"))
check("plug: invented product slug is rejected",
      plug_problems("here\n\nhttps://digitalstackr.gumroad.com/l/threads-revenue-ladder"))
check("plug: a CTA with no link is rejected",
      plug_problems("you should really buy my guide, it is great"))
check("plug: unbacked figure is rejected (a reply has no screenshot)",
      plug_problems("i made $1,638.53 doing this\n\n" + FDE_URL))
check("plug: banned emoji is rejected",
      plug_problems("here you go \U0001f525\n\n" + FDE_URL))
check("plug: over the 490 char cap is rejected",
      plug_problems("x" * 500 + "\n\n" + FDE_URL))
# The question check must look at the PROSE, not the raw string: a plug always
# ends with its URL, so a trailing-"?" test on the whole text can never fire.
check("plug: question before the link is still caught",
      plug_problems("want the system?\n\n" + FDE_URL))
check("plug: a legitimate CTA passes clean",
      plug_problems("getting a lot of dms asking how this works.\n\n"
                    "easier to put it in one place than answer it fifty "
                    "times.\n\n" + FDE_URL) == [])

# Every plug attach_plugs.py actually writes must survive the validator, or the
# next queue commit is blocked.
import json as _json, pathlib as _pl
_q = _json.load(open(_pl.Path(__file__).parent / "queue.json", encoding="utf-8"))
_plugged = [e for e in _q if (e.get("auto_plug") or {}).get("status") == "pending"]
check(f"plug: all {len(_plugged)} attached CTAs pass the validator",
      len(_plugged) > 0 and
      [p for p in vcm.validate(_q) if "auto_plug" in p] == [])

# attach_plugs must never hand a beginner freebie to a post that just showed
# proof - including proof stated as a headcount rather than a dollar figure.
import attach_plugs as apl
check("plug: dollar receipt gets the product CTA",
      apl.offer_for({"text": "$1,673.63 from 86 people.\n\neight months ago i "
                             "had a phone and nothing else.",
                     "image_file": "x.png"}) == "product")
check("plug: headcount receipt gets the product CTA",
      apl.offer_for({"text": "225 people bought a PDF from a teenager with no "
                             "audience.", "image_file": "x.png"}) == "product")
check("plug: a genuine beginner post gets the freebie CTA",
      apl.offer_for({"text": "the same little phone keyboard i used at zero is "
                             "the one i'm typing on now.",
                     "image_file": "x.png"}) == "freebie")

print(f"\n==== RESULT: {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
