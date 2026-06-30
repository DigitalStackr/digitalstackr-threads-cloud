# DigitalStackr Threads — Cloud Scheduler

24/7 automated posting to @digitalstackr (MAIN) and @thedigitalstackr (TDS) via Meta's official Threads API. Runs on GitHub Actions, fires posts every 5 minutes regardless of whether any laptop is on.

---

## How it works

1. You add posts to the queue (via the **"Add Post to Queue"** workflow on the Actions tab — fill a form, it commits the entry to `queue.json`).
2. Every 5 minutes, GitHub Actions runs `scheduler.py`. It checks `queue.json` for posts whose scheduled time is within the last 20 minutes.
3. If any are due, it posts them to Threads via the API and marks them as `posted` in the queue.
4. All activity is logged to `log.txt` (committed back to the repo so you can review).

---

## Daily usage

### Schedule a post for later
1. Go to the **Actions** tab on the repo
2. Click **"Add Post to Queue"** in the left sidebar
3. Click **"Run workflow"** button (top right)
4. Fill the form:
   - **account:** MAIN or TDS
   - **text:** your post text (line breaks work — just hit Enter)
   - **scheduled_time:** `YYYY-MM-DD HH:MM` in Berlin time (e.g. `2026-07-01 18:00`)
   - **image_file:** filename if image post (leave blank for text-only) — image must already be uploaded to `images/` folder
5. Click **"Run workflow"** → done. Entry appears in `queue.json` within ~30 seconds.

### Post immediately (no scheduling)
1. **Actions** → **"Post Now (immediate, no scheduling)"** → **"Run workflow"**
2. Same form, no time field
3. Post fires within ~1 minute

### Add an image
1. Go to the `images/` folder on github.com
2. Click **"Add file" → "Upload files"**
3. Drag image → commit
4. Reference filename in the queue/post workflow

### Check what's scheduled
Open `queue.json` in the repo. Entries with `"status": "pending"` are upcoming. `"posted"` is done.

### Check what's happened
Open `log.txt` in the repo. Every scheduler tick adds entries.

---

## Files

| File | Purpose |
|------|---------|
| `scheduler.py` | The cron-fired worker — checks queue, fires due posts |
| `post_text.py` | Text posting function |
| `post_image.py` | Image posting (uploads to uguu.se, then posts) |
| `queue_add.py` | Adds a post to queue.json (called by workflow) |
| `post_now.py` | Fires a single post immediately (called by workflow) |
| `queue.json` | The queue. Auto-managed by workflows. |
| `log.txt` | Scheduler activity log. Auto-created. |
| `requirements.txt` | Python deps (just `requests`) |
| `.github/workflows/scheduler.yml` | Runs every 5 min |
| `.github/workflows/post-now.yml` | Manual immediate post |
| `.github/workflows/queue-add.yml` | Manual add-to-queue form |
| `images/` | Real screenshots for image posts (committed to repo) |

---

## Token rules

- Tokens live in GitHub Secrets (`THREADS_MAIN_TOKEN`, `THREADS_TDS_TOKEN`)
- Encrypted at rest, never visible in logs or to anyone
- Long-lived tokens expire in 60 days — refresh them in Meta dashboard and update the secrets

---

## Cron timing notes

- Cron is `*/5 * * * *` (every 5 minutes)
- GitHub Actions cron has up to ~15 min variance on free tier during peak load
- Scheduler uses a 20-minute catch-up window so any delayed post still fires
- For peak slot posts (e.g. 8 PM viral try), schedule it for 7:55 PM Berlin to ensure it lands before 8 PM EST equivalent

---

## Disabling

To pause all posting: go to **Actions** tab → click the **"Threads Scheduler"** workflow → menu top-right → **"Disable workflow"**.

To unschedule a pending post: edit `queue.json` directly on github.com (find the entry, change `"status": "pending"` to `"status": "cancelled"`, commit).
