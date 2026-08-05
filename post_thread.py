"""
Long-form Threads publishing: one root post continued in its own replies.

WHY THIS EXISTS
  The July 2026 platform data is unambiguous about format:
      long form thread   12,899 avg views
      long post             963
      short post            729
  Every one of the top-10 posts that month was a long-form thread, and the money
  accounts that grew (@climbtowealth, @pooravbolar) publish almost nothing else.
  We had published ZERO, not by choice - post_text() had no reply_to_id, so the
  format was physically unreachable from this codebase.

MECHANICS
  Part 1 publishes normally and becomes the root. Each later part publishes with
  reply_to_id pointing at the PREVIOUS part, which is what Threads' own UI does
  when you continue a thread. Verified against the live API on 2026-08-05:
  the reply comes back with is_reply=true and root_post pointing at part 1.

PARTIAL FAILURE IS THE INTERESTING CASE
  A thread that dies at part 4 of 7 must never restart from part 1 - that would
  publish part 1 twice. So every published part id is recorded as we go, and a
  retry resumes from the first part that has no id yet, re-parenting onto the
  last part that does. This mirrors how fire_entry() never re-sends a target
  that already succeeded.
"""
import time

from post_text import post_text
from post_image import post_image

# Threads applies its own rate limiting; a short gap between parts also makes the
# thread land in order rather than racing.
PART_DELAY_SEC = 3

# A thread is a handful of posts, not a blog. Beyond this something has gone wrong
# in generation and we'd rather fail loudly than spray 40 posts at the timeline.
MAX_PARTS = 12


class ThreadPartialError(Exception):
    """A thread failed partway. Carries the ids that DID publish so the retry can
    resume from the right part instead of posting a second root."""

    def __init__(self, published, failed_index, cause):
        self.published = list(published)
        self.failed_index = failed_index
        self.cause = cause
        super().__init__(
            f"thread failed at part {failed_index + 1} "
            f"({len(self.published)} part(s) already live): {cause}"
        )


def post_thread(account, parts, image_file=None, image_dir="images",
                published=None, delay=PART_DELAY_SEC):
    """Publish `parts` (list of strings) as one connected Threads chain.

    image_file, if given, is attached to PART 1 only - the hook carries the visual,
    the rest is text. Returns the list of published post ids, part 1 first.

    `published` is the ids already live from a previous attempt; publishing resumes
    after them. Pass the list back in on retry and part 1 is never re-sent.
    """
    if not parts:
        raise ValueError("post_thread called with no parts")
    if len(parts) > MAX_PARTS:
        raise ValueError(f"thread has {len(parts)} parts, max is {MAX_PARTS}")

    ids = list(published or [])
    if len(ids) >= len(parts):
        return ids  # already fully published - nothing left to do

    for index in range(len(ids), len(parts)):
        text = parts[index]
        parent = ids[-1] if ids else None

        try:
            if index == 0:
                # Root. Only the root carries media; replies stay text so the thread
                # reads as one continuous piece rather than a gallery.
                if image_file:
                    post_id = post_image(account, text, image_file, image_dir=image_dir)
                else:
                    post_id = post_text(account, text)
            else:
                post_id = post_text(account, text, reply_to_id=parent)
        except Exception as e:
            # Carry the parts that DID publish out with the error. Without this the
            # caller cannot tell a thread that died at part 1 from one that died at
            # part 6, and the retry would republish part 1 as a second root post.
            raise ThreadPartialError(ids, index, e) from e

        ids.append(post_id)

        # No sleep after the final part - nothing is waiting on it.
        if index < len(parts) - 1:
            time.sleep(delay)

    return ids
