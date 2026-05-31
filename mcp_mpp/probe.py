"""`python -m mcp_mpp.probe` — discovery / smoke-test helper.

Calls a few read endpoints with the seeded auth and prints a compact SHAPE of
each response (keys/types, truncated strings) so contracts can be confirmed
without dumping tokens or other players' personal data.

Pass a championship id to also dump its calendar, e.g.:
    uv run python -m mcp_mpp.probe 8
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .client import AuthError, MppApiError, MppClient

_SENSITIVE = ("token", "email", "phone", "password", "refresh", "access")


def shape(o: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "…"
    if isinstance(o, dict):
        return {
            k: ("<redacted>" if any(s in k.lower() for s in _SENSITIVE) else shape(v, depth + 1))
            for k, v in list(o.items())[:30]
        }
    if isinstance(o, list):
        return [shape(o[0], depth + 1), f"… ({len(o)} items)"] if o else []
    if isinstance(o, str):
        return o if len(o) <= 40 else f"<str {len(o)}>"
    return o


def probe(name: str, fn) -> None:
    print(f"\n=== {name} ===")
    try:
        print(json.dumps(shape(fn()), indent=2, ensure_ascii=False))
    except (MppApiError, AuthError) as exc:
        print(f"ERROR: {exc}")


def main() -> None:
    championship_id = sys.argv[1] if len(sys.argv) > 1 else None
    with MppClient() as c:
        probe("GET /user-contests (my_leagues)", c.my_leagues)
        probe("GET /championships-current-matches", c.current_matches)
        if championship_id:
            probe(f"GET /championship-calendar/{championship_id}", lambda: c.championship_calendar(championship_id))
            probe(
                f"GET /championship-calendar/{championship_id}/next-game-weeks",
                lambda: c.next_game_weeks(championship_id),
            )
    print("\n(done — shapes only, no secrets/PII printed in full)", file=sys.stderr)


if __name__ == "__main__":
    main()
