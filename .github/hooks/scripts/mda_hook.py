#!/usr/bin/env python3
"""Single entry point for all Copilot CLI hook events: mda_hook.py <eventName> (payload on stdin)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from mda.hooks import dispatch  # noqa: E402


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    result = dispatch(event, payload)
    if result:
        sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
