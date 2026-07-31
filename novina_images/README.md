# novina_images/

Screenshots for the **Novina** brand (`@bynovinaa`) only.

## Why this is a separate folder

DigitalStackr's screenshots name DigitalStackr's products — "Faceless Digital
Empire", "Done-For-You Digital Business Setup" — and several carry a STACKR
watermark. Posting one of those on a Novina account is an instant credibility
hole for anyone who looks closely.

**Nothing from `images/` is ever posted to Novina, and nothing here is ever
posted to DigitalStackr.** The scheduler picks the folder from the account, so
this can't happen by accident.

## How to add screenshots

On github.com, open this folder → **Add file** → **Upload files** → drag them in
→ **Commit changes**. That's it — they're live immediately over the raw URL.

## Before a screenshot can be used

Every image must be **opened and recorded** in `novina_manifest.json` first —
what number it shows, what kind it is. Filenames lie (we've been burned: one
`.png` in this repo is actually an MP4). An unlisted image is refused by
`validate_content.py`, so a caption can never cite a figure the screenshot
doesn't show.

Tell Claude when you've uploaded and they'll be opened, verified and added.

## What works well here

Per the Novina brief this audience responds to words and white space more than
screenshots — proof posts are **the exception, not the norm** (~2 of 5 posts/day).

Best kinds:
- Payout notifications (PayPal / Gumroad) — no product name visible
- Dashboard totals — just the figure and sale count
- Sale notifications **for The Silk Thread** ($17), not DigitalStackr products

## Rules that still apply

- Real screenshots only. Never AI-generated.
- Every `$` figure in a caption must match the attached screenshot exactly.
- No location references.
- Slightly larger numbers are fine, but keep them occasional — the small real
  ones convert better with this audience.
