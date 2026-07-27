"""
Connection diagnostic for every posting platform.

Runs INSIDE GitHub Actions so it can read the repo secrets. It prints only
non-secret identifiers (account names, ids, granted scopes, expiry) — never a
token value. Safe to read in a public Actions log.

Usage:  python check_connections.py
"""
import os
import sys

import requests

GRAPH = "https://graph.facebook.com/v21.0"
OK, WARN, BAD = "[OK]", "[!!]", "[XX]"


def _get(url, params, timeout=30):
    r = requests.get(url, params=params, timeout=timeout)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"error": {"message": f"non-JSON response ({r.status_code})"}}


def check_facebook():
    """Verify the Page token works and points at the expected Page."""
    print("\n=== FACEBOOK PAGE ===")
    token = os.environ.get("FB_PAGE_TOKEN")
    page = os.environ.get("FB_PAGE_ID")
    if not token or not page:
        print(f"{BAD} FB_PAGE_TOKEN / FB_PAGE_ID not set in the environment")
        return None, None

    st, data = _get(f"{GRAPH}/{page}", {"fields": "id,name,category,link", "access_token": token})
    if st >= 300 or "error" in data:
        print(f"{BAD} Page lookup failed: {data.get('error', data)}")
        return None, None

    print(f"{OK} Page connected: '{data.get('name')}' (id {data.get('id')})")
    print(f"     category: {data.get('category')}  link: {data.get('link')}")

    # Token scopes + expiry (debug_token accepts the page token for both fields)
    st, dbg = _get(f"{GRAPH}/debug_token", {"input_token": token, "access_token": token})
    info = (dbg or {}).get("data", {})
    if info:
        exp = info.get("expires_at", 0)
        print(f"     token type: {info.get('type')}  app_id: {info.get('app_id')}")
        print(f"     expires_at: {'NEVER (non-expiring)' if exp == 0 else exp}")
        scopes = info.get("scopes", [])
        print(f"     granted scopes: {', '.join(scopes) if scopes else '(none reported)'}")
        for needed in ("pages_manage_posts", "pages_read_engagement"):
            mark = OK if needed in scopes else WARN
            print(f"       {mark} {needed}")
    return token, page


def check_instagram(token, page):
    """Verify an IG Business/Creator account is linked to the Page and publishable."""
    print("\n=== INSTAGRAM ===")
    if not token or not page:
        print(f"{BAD} skipped — no working Page token")
        return

    st, data = _get(
        f"{GRAPH}/{page}",
        {"fields": "instagram_business_account{id,username,name,followers_count,media_count}",
         "access_token": token},
    )
    if st >= 300 or "error" in data:
        print(f"{BAD} lookup failed: {data.get('error', data)}")
        return

    ig = data.get("instagram_business_account")
    if not ig:
        print(f"{BAD} NO Instagram Business account is linked to this Page.")
        print("     -> Link @digitalstackr (Business/Creator) to the Page, then re-run.")
        return

    print(f"{OK} IG account linked: @{ig.get('username')} (id {ig.get('id')})")
    print(f"     name: {ig.get('name')}  followers: {ig.get('followers_count')}  media: {ig.get('media_count')}")
    print(f"     >>> IG_USER_ID to store as a secret: {ig.get('id')}")

    # Publishing scopes are what actually gate posting.
    st, dbg = _get(f"{GRAPH}/debug_token", {"input_token": token, "access_token": token})
    scopes = (dbg or {}).get("data", {}).get("scopes", [])
    print("     publishing scopes:")
    ready = True
    for needed in ("instagram_basic", "instagram_content_publish"):
        has = needed in scopes
        ready = ready and has
        print(f"       {OK if has else BAD} {needed}")
    if not ready:
        print(f"{WARN} Token is missing IG publishing scope(s) — a NEW token must be generated")
        print("     with instagram_basic + instagram_content_publish granted.")
    else:
        print(f"{OK} Token can publish to Instagram.")

    # Content Publishing API quota (25 posts / 24h rolling).
    st, q = _get(f"{GRAPH}/{ig.get('id')}/content_publishing_limit",
                 {"fields": "config,quota_usage", "access_token": token})
    if st < 300 and "error" not in q:
        d = (q.get("data") or [{}])[0]
        print(f"     publishing quota used: {d.get('quota_usage')} / "
              f"{(d.get('config') or {}).get('quota_total', 25)} per 24h")


def check_threads():
    print("\n=== THREADS ===")
    for label in ("MAIN", "TDS"):
        tok = os.environ.get(f"{label}_TOKEN")
        if not tok:
            print(f"{BAD} {label}_TOKEN not set")
            continue
        st, data = _get("https://graph.threads.net/v1.0/me",
                        {"fields": "id,username", "access_token": tok})
        if st >= 300 or "error" in data:
            print(f"{BAD} {label}: {data.get('error', data)}")
        else:
            print(f"{OK} {label}: @{data.get('username')} (id {data.get('id')})")


def main():
    print("DigitalStackr — platform connection check")
    token, page = check_facebook()
    check_instagram(token, page)
    check_threads()
    print("\nDone. (No token values are printed above.)")


if __name__ == "__main__":
    sys.exit(main())
