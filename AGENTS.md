# AGENTS.md — DigitalStackr

Read this before touching anything. It is the shared brief for every agent working
on this repo (Claude Code, Codex, anything else). It is kept current deliberately:
if you change how the system works, update this file in the same commit.

Everything below is **measured**, not assumed. Where a number appears, it came
from the Gumroad API, the Threads Graph API, or the GitHub API — not from memory.

---

## 1. What this business is

DigitalStackr — a faceless digital-product brand run by one person (Shawn, 19,
works from a phone). Sells guides and a done-for-you service. Threads is the only
acquisition channel that has ever produced revenue.

**Verified financials** *(Gumroad API, 522 records, as of 2026-08-20)*

```
lifetime gross      $1,954.20
gumroad fees          $310.56
net                 $1,643.64
PAID orders                65
FREE downloads            457   <- the dashboard counts these as "sales"
refunds                     0
chargebacks                 0
rating                   4.9 from 17 verified reviews
```

**By product**

| Product | Price | Orders | Revenue | Avg |
|---|---|---|---|---|
| Faceless Digital Empire | $27 | 36 | $926.85 | $25.75 |
| Done-For-You Setup | $147 | 7 | $749.70 | **$107.10** |
| Threads Revenue Ladder | $9 | 12 | $145.65 | $12.14 |
| 2-Week Mentorship | $97 | 3 | $115.00 | $38.33 |

**By traffic source** *(paid orders only)*

```
                  paid / total records   revenue     what gets linked there
beacons.ai        14 / 281               $489.32     bio -> mostly free magnets
l.threads.com     15 /  17               $467.00     in-post product links
direct            18 /  94               $370.02     typed / no referrer
gumroad.com       13 /  70               $366.86     Gumroad Discover
```

**Read the referrer table carefully — it is easy to misread, and was misread
once already.** A Gumroad record exists only for a TRANSACTION (a paid order or a
free download). Someone who clicks and buys nothing creates no record at all.

So `15 paid of 17 records` on l.threads.com is **the paid share of transactions**,
NOT a conversion rate. beacons.ai looks weaker only because the free magnets are
linked from the bio, and every free download creates a record.

What the data does support: **direct product links in posts have produced $467
from 17 transactions, against $489 from 281 via the bio.** Direct links carry
paid intent; the bio carries free intent. They do different jobs.

What it does NOT support: any per-visitor conversion claim. **We have no click
data from any platform** — see §4.

---

## 2. Architecture

```
cron-job.org ─┐
GitHub cron  ─┴→ Actions (*/5 min) → scheduler.py
                   ├ queue.json  (the state; ~630 entries)
                   ├ per-target isolation, self-heal x5, semantic merge
                   ├ dedupe_guard.py   asks Threads before every send
                   ├ auto_plug.py      CTA reply at 1500 views / 20 likes
                   ├ telegram_faq.py   DM bot
                   ├ runway_check.py   warns when the queue nears empty
                   └ commits queue.json back
```

**Key files**

| File | Does |
|---|---|
| `scheduler.py` | Fires due entries. Per-target isolation, self-heal, catch-up. |
| `validate_content.py` | **Nothing queues without passing this.** Run it before every commit. |
| `image_manifest.json` | What each screenshot actually contains. Verified by opening the file. |
| `dedupe_guard.py` | Prevents double-posting. See §4. |
| `merge_queue.py` | Semantic merge when two runs collide. `posted` always wins. |
| `runway_check.py` | Alerts on low runway or publishing silence. |
| `post_*.py` | One per platform: threads, x, telegram, facebook, instagram, tiktok. |

**Live platforms:** Threads (MAIN + TDS), X, Telegram.
**Dormant:** Instagram (Reels-only, no content), Facebook, TikTok (in review).

---

## 3. Content rules — these are enforced in code

Do not weaken these without measured evidence. Each exists because something
broke.

1. **Real screenshots only.** Never AI-generated. Never a figure that is not
   visible in the attached image. `image_manifest.json` is the authority.
2. **Never infer an image's contents from its filename.** Open it. A file was
   silently replaced once and two queued posts cited a number the new image did
   not show.
3. **No location references** — no cities, countries, transit. This includes
   *visually*: one screenshot was blocked because a transit widget was in shot.
4. **Max 490 chars** on Threads. X Premium allows far more — long-form there.
5. **Never end a post on a question.** Measured failure.
6. **No engagement bait.** "drop an emoji", "tag someone", "comment below".
7. **Hype emoji rationed** — 😭 💸 🥹 allowed, max one per 6 posts per account.
8. **Never claim daily earnings** unless the screenshot literally says "today".

---

## 4. Things that already went wrong — do not recreate them

**Double-posting.** GitHub cron and cron-job.org fire ~60s apart. The second run
reads a `queue.json` the first has not finished pushing, sees `pending`, and
publishes again. 9 confirmed duplicates, 58–153s apart. `concurrency:` does not
reliably serialise them and `merge_queue.py` only protects the record.
**Fix: `dedupe_guard.py` asks Threads directly before every send.** Any new guard
built on our own state will fail the same way — our state is what goes stale.

**log.txt rebase conflicts.** Two runs appending to the same tracked file
conflicted at EOF every time, failing the run. **Never add a committed file
without a conflict-free merge rule.** This is why `runway_check.py` throttles by
clock time rather than a state file.

**Conflict markers fed to the JSON merger.** The workflow copied `queue.json`
during a conflicted rebase, so `merge_queue.py` got `<<<<<<< HEAD` and died.
Abort first, then read from HEAD.

**The queue ran dry (Aug 14–18).** Scheduler stayed 100% green and published
nothing for 94 hours. Views halved. **A green pipeline with an empty queue looks
identical to a healthy one** — that is what `runway_check.py` exists for.

**Long-form threads (Aug 8–11).** Reach halved across *every* format, not just
threads — likely the burst of 7–11 posts in ~21s, 2–3x/day. Reverted.
`post_thread.py` still works but is not in use.

**Attribution by redirect — TESTED AND FAILED (2026-08-14).** Two live test
purchases through a redirect on digitalstackr.com carrying
`referrer=unsafe-url`. Gumroad recorded `direct` both times — no referrer at all,
not even the bare origin. Threads and Beacons send origin only
(`https://l.threads.com/`, `https://beacons.ai/`), stripping path and query, so a
tracking parameter never survives the hop.

**Consequence: post-level attribution is not achievable.** Do not build UTM or
campaign-ID schemes that depend on it, and do not plan metrics around "unique
link clicks" — no platform in this stack reports them. Attribution stops at the
funnel-path level (which domain), and that is already available for free.

**X capped at 280.** The validator was raised for Premium; `post_x.py` was not.
Every long post failed at send and cascaded to `expired`.

---

## 5. What measurably works

**Caption structures**, by median views on MAIN (241 posts measured):

| Structure | Median | Best | Example |
|---|---|---|---|
| Celebration | — | **27,500** | *"ITS OFFICIAL!!!!! [FIGURE] 🥹"* — best follows-per-view |
| Someone paid me | **2,141** | 3,468 | *"someone paid $147 for me to build the whole thing"* |
| Happened without me | 1,158 | 19,100 | *"sold while i was asleep. 70 times today."* |
| Identity / defiance | 965 | **26,423** | *"not a genius. not connected. not lucky."* |
| Quoted objection | 786 | 23,700 | *"nobody buys PDFs anymore." / "$27. this afternoon."* |
| **Plain receipt** | **349** | — | *"$224.52 from 24 people."* ← was 61% of output |

**The rule underneath:** every winner contains a *second person* — someone who
paid, doubted, or trusted. A number alone is a fact. A number with a human in it
is a story.

**Framing beats figure size.** `$382` framed as a milestone did **18,600 views**.
The same `$382` stated plainly medians **274**. 68x, same number.

**Images beat text-only 2:1** (median 535 vs 262).

---

## 6. Current state and priorities

**Now:** ~$1,954 lifetime. Target is $10k profit in 90 days. That needs a higher
price point — 111 orders/month at $30 is not reachable on 400k views; ~7/month at
$497 is a different problem.

**The structural gap:** there is no capture layer. 52,700 views per paid sale,
because every post asks a cold stranger to buy in one hop. Free offers convert
**7x better** than paid (457 vs 65) and 370 of those became email subscribers.

**Agreed direction (not yet built):**
1. Auto-plug switches from selling the $27 product to offering the free magnet
2. A fixed 7-email Kit sequence sells FDE to new subscribers
3. Replies to "how?" comments hand over the free thing, not a pitch
4. A $497 tier (DFY + first 30 days of content) sits above the $147

---

## 7. Working agreements

- **Never modify production without saying what and why first.**
- **Run `python validate_content.py` before any queue commit.** It exits 1 on
  violation and it has caught real errors every single time it has been run.
- **Run `python test_local.py`** before committing scheduler changes. 123 tests.
- **Never commit secrets or customer PII.** `.env` is gitignored; Gumroad exports
  contain buyer emails and are gitignored too.
- **Verify, do not assume.** Every claim in this file was checked against a live
  API. If you cannot check something, say so rather than asserting it.
- **Update this file** when you change how the system works.
