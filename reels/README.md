# reels/

Drop finished vertical videos here. The scheduler posts them to **Instagram Reels**
(and later Facebook Reels) by public raw URL — same mechanism as `images/`.

## Rules

- **Format:** `.mp4` (H.264 + AAC). `.mov` also works but is bigger.
- **Aspect:** 9:16 vertical, 1080x1920. This is what the ardenvow Remotion project
  already renders.
- **Length:** 3s - 15min. Short (7-20s) performs best.
- **Size:** keep under ~50MB. GitHub hard-caps files at 100MB, and the file is
  fetched over a public URL by Meta.
- **Filename:** no spaces if you can avoid it — `hook-payout-01.mp4` beats
  `my reel (final)(2).mp4`. Spaces work (they get URL-encoded) but are noisy.

## How a reel gets posted

Add a queue entry with a `video_file` pointing at a file in this folder:

```json
{
  "id": 400,
  "text": "caption goes here",
  "video_file": "hook-payout-01.mp4",
  "scheduled_time": "2026-07-28T20:00:00+02:00",
  "status": "pending",
  "targets": [{ "platform": "instagram" }]
}
```

One entry can fan out — screenshot to Threads/Facebook, reel to Instagram:

```json
{
  "id": 401,
  "text": "shared caption",
  "image_file": "3.9k gumroad ss.png",
  "scheduled_time": "...",
  "status": "pending",
  "targets": [
    { "platform": "threads", "account": "MAIN" },
    { "platform": "facebook" },
    { "platform": "instagram", "video_file": "hook-payout-01.mp4" }
  ]
}
```

## Instagram is REELS ONLY

Screenshots are never posted to Instagram. Every proof screenshot in `images/` is a
wide desktop crop (1.91-3.12 aspect) and Instagram's feed only accepts 0.80-1.91 —
Meta rejects them (error 36003). The scheduler refuses an IG target with no
`video_file` before it ever reaches the API.

## Content rules still apply

- Real footage/screenshots only — never AI-generated imagery.
- Every `$` number spoken or shown must match the underlying proof exactly.
- No location references (no cities, transit, countries).
