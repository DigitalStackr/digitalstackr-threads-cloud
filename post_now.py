"""
Fires a single post immediately. Called by the 'Post Now' GitHub Actions workflow.

Usage:
    python post_now.py <account> <text> [image_filename]
"""
import sys


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: post_now.py <account> <text> [image_filename]")
        sys.exit(1)

    account = sys.argv[1].strip()
    text = sys.argv[2]
    image = sys.argv[3].strip() if len(sys.argv) > 3 and sys.argv[3].strip() else None

    if account not in ("MAIN", "TDS"):
        print(f"Account must be MAIN or TDS, got: {account}")
        sys.exit(1)

    if image:
        from post_image import post_image
        thread_id = post_image(account, text, image)
    else:
        from post_text import post_text
        thread_id = post_text(account, text)

    print(f"POSTED — thread_id={thread_id}")


if __name__ == "__main__":
    main()
