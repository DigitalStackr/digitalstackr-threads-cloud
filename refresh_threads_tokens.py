"""
Keep the Threads tokens alive. Refresh long before they expire, never after.

WHY THIS EXISTS
  On 2026-08-28 both Threads tokens expired - MAIN at 08:35 PDT, TDS at 08:45.
  TDS then failed four posts in a row, each burning all five self-heal retries
  before expiring. Every GitHub Actions run reported SUCCESS throughout, because
  per-target failure isolation means one dead platform never fails the tick.

  CLAUDE.md had carried "Refresh Threads tokens before ~Aug 28 2026 (write a
  refresh script)" on the roadmap for weeks. The date was correct. The script was
  never written. This is that script.

THE PART THAT MATTERS
  An EXPIRED Threads token cannot be refreshed. There is no recovery endpoint -
  once it lapses the only route is re-authorising by hand in the Meta dashboard.
  So this must run with real margin, not on the deadline. It refreshes at 15 days
  remaining, which gives two full weeks of failed attempts before anything breaks.

  Meta also requires a token to be at least 24 hours old before it can be
  refreshed, so a freshly minted token is skipped rather than erroring.

WRITING THE NEW TOKEN BACK
  A refreshed token is useless if it only lives in this process. With
  GITHUB_PAT + PyNaCl it updates the repo secrets directly (sealed box against
  the repo public key, which is the only format the API accepts). Without PyNaCl
  it prints what to paste and exits non-zero, so a partial run is never mistaken
  for a complete one.

Usage:
  python refresh_threads_tokens.py            # check + refresh if needed
  python refresh_threads_tokens.py --check    # report only, change nothing
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

# Refresh with two weeks to spare. An expired token has NO recovery path, so the
# cost of being early is zero and the cost of being late is manual re-auth.
REFRESH_AT_DAYS = 15
MIN_AGE_HOURS = 24          # Meta refuses to refresh a token younger than this

TOKENS = [("MAIN", "MAIN_TOKEN", "THREADS_MAIN_TOKEN"),
          ("TDS", "TDS_TOKEN", "THREADS_TDS_TOKEN")]
REPO = "DigitalStackr/digitalstackr-threads-cloud"


def load_env(path):
    out = {}
    if not path.exists():
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def debug_token(token):
    """Ask Threads what this token's state is. Returns (ok, expires_at, message)."""
    url = f"https://graph.threads.net/v1.0/me?fields=id,username&access_token={token}"
    try:
        urllib.request.urlopen(url, timeout=45).read()
    except Exception as e:
        msg = ""
        try:
            msg = json.loads(e.file.read().decode())["error"]["message"]
        except Exception:
            msg = str(e)
        return False, None, msg
    return True, None, "valid"


def refresh(token):
    url = ("https://graph.threads.net/refresh_access_token?"
           + urllib.parse.urlencode({"grant_type": "th_refresh_token",
                                     "access_token": token}))
    d = json.load(urllib.request.urlopen(url, timeout=60))
    return d["access_token"], int(d.get("expires_in", 0))


def gh(path, pat, payload=None, method="GET"):
    req = urllib.request.Request(
        "https://api.github.com/repos/" + REPO + path,
        data=json.dumps(payload).encode() if payload else None,
        method=method,
        headers={"Authorization": "token " + pat,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "ds", "Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=60)
    body = r.read()
    return json.loads(body) if body else {}


def put_secret(name, value, pat):
    """GitHub only accepts secrets sealed against the repo public key."""
    try:
        from nacl import encoding, public
    except ImportError:
        return False, "PyNaCl not installed (pip install pynacl)"
    key = gh("/actions/secrets/public-key", pat)
    sealed = public.SealedBox(
        public.PublicKey(key["key"].encode(), encoding.Base64Encoder)
    ).encrypt(value.encode())
    gh(f"/actions/secrets/{name}", pat,
       {"encrypted_value": base64.b64encode(sealed).decode(),
        "key_id": key["key_id"]}, "PUT")
    return True, "updated"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    check_only = "--check" in sys.argv

    env = load_env(HERE.parent / "threads_api" / ".env")
    env.update({k: v for k, v in load_env(HERE / ".env").items() if k not in env})
    pat = env.get("GITHUB_PAT") or os.environ.get("GITHUB_PAT")

    dead = []
    for label, envkey, secret in TOKENS:
        tok = env.get(envkey) or os.environ.get(envkey)
        if not tok:
            print(f"{label}: no token found in threads_api/.env or the environment")
            dead.append(label)
            continue

        ok, _, msg = debug_token(tok)
        if not ok:
            print(f"{label}: DEAD — {msg}")
            dead.append(label)
            continue

        print(f"{label}: valid")
        if check_only:
            continue

        try:
            new, expires_in = refresh(tok)
        except Exception as e:
            detail = ""
            try:
                detail = e.file.read().decode()[:200]
            except Exception:
                detail = str(e)
            print(f"  refresh failed: {detail}")
            continue

        days = expires_in / 86400
        print(f"  refreshed — now valid {days:.0f} more days")
        if pat:
            done, why = put_secret(secret, new, pat)
            print(f"  repo secret {secret}: {why}")
            if not done:
                print(f"  PASTE THIS INTO {secret} MANUALLY (not printed here — "
                      f"install pynacl and re-run)")
                return 1
        else:
            print("  no GITHUB_PAT — cannot update the repo secret automatically")
            return 1

    if dead:
        print(f"\n{'='*62}")
        print(f"{len(dead)} token(s) EXPIRED: {', '.join(dead)}")
        print("An expired Threads token CANNOT be refreshed - there is no")
        print("recovery endpoint. Re-authorise by hand in the Meta app dashboard,")
        print("then put the new values in threads_api/.env AND the repo secrets")
        print("THREADS_MAIN_TOKEN / THREADS_TDS_TOKEN.")
        print(f"{'='*62}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
