"""Resolve a telegram_offset.json conflict between two concurrent scheduler runs.

The offset only ever moves forward, so the higher value is always the correct
resolution. Kept as its own file (rather than inlined in the workflow) because a
heredoc inside a YAML block scalar broke the workflow parser once already.

Usage: python merge_offset.py OURS.json CURRENT.json
       -> writes the max offset into CURRENT.json
"""
import json
import sys


def load(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            return int(json.load(f).get("offset", 0))
    except Exception:
        return 0


def main() -> int:
    ours, current = sys.argv[1], sys.argv[2]
    best = max(load(ours), load(current))
    with open(current, "w", encoding="utf-8") as f:
        json.dump({"offset": best}, f, indent=2)
        f.write("\n")
    print(f"merged telegram offset -> {best}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
