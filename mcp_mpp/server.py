"""MCP server exposing Mon Petit Prono tools.

Write mode is immediate: `submit_forecast` / `submit_forecasts` send the PATCH
right away with no confirmation step. The call is idempotent, so a prediction
can be corrected by calling again before kickoff. Every write is logged to
stderr.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import AuthError, MppApiError, MppClient

mcp = FastMCP("mcp-mpp")


def _log(msg: str) -> None:
    print(f"[mcp-mpp] {msg}", file=sys.stderr, flush=True)


def _run(fn) -> Any:
    """Call a client method, mapping known errors to readable strings."""
    try:
        with MppClient() as c:
            return fn(c)
    except AuthError as exc:
        return {"error": "auth", "message": str(exc)}
    except MppApiError as exc:
        return {"error": "api", "status": exc.status, "message": str(exc)}


@mcp.tool()
def list_my_leagues() -> Any:
    """List the leagues/challenges this account belongs to.

    Returns each league's contest_id, title, championship_id, current ranking and
    points. Use the championship_id with `upcoming_game_weeks` to find matches to
    predict.
    """
    return _run(lambda c: c.my_leagues())


@mcp.tool()
def championship_calendar(championship_id: int) -> Any:
    """Full calendar of a championship: game weeks with their match ids and dates."""
    return _run(lambda c: c.championship_calendar(championship_id))


@mcp.tool()
def upcoming_game_weeks(championship_id: int) -> Any:
    """Upcoming game weeks of a championship (each with its match ids and dates)."""
    return _run(lambda c: c.next_game_weeks(championship_id))


@mcp.tool()
def get_match(match_id: str) -> Any:
    """Match detail: teams (club ids), kickoff date, odds and stats.

    match_id e.g. "mpp_championship_match_2608241".
    """
    return _run(lambda c: c.match(match_id))


@mcp.tool()
def get_my_forecast(match_id: str, scope: str = "general") -> Any:
    """Read the account's current prediction for a match."""
    return _run(lambda c: c.my_forecast(match_id, scope=scope))


@mcp.tool()
def submit_forecast(
    match_id: str, home_score: int, away_score: int, scope: str = "general"
) -> Any:
    """Submit or edit a score prediction. Sends immediately (no confirmation).

    match_id e.g. "mpp_championship_match_2608241". `scope` "general" is your
    universal forecast, counted across every league you are in.
    """
    _log(f"SUBMIT {match_id} -> {home_score}-{away_score} (scope={scope})")
    result = _run(lambda c: c.submit_forecast(match_id, home_score, away_score, scope=scope))
    _log(f"  result: {json.dumps(result)[:200]}")
    return result


@mcp.tool()
def submit_forecasts(forecasts: list[dict[str, Any]], scope: str = "general") -> Any:
    """Submit several predictions at once.

    forecasts: [{ "match_id": str, "home_score": int, "away_score": int }, ...]
    Returns a per-match result; one failure does not stop the others.
    """
    results = []
    with MppClient() as c:
        for f in forecasts:
            mid = f["match_id"]
            hs, as_ = int(f["home_score"]), int(f["away_score"])
            _log(f"SUBMIT {mid} -> {hs}-{as_} (scope={scope})")
            try:
                res = c.submit_forecast(mid, hs, as_, scope=scope)
                results.append({"match_id": mid, "ok": True, "result": res})
            except (MppApiError, AuthError) as exc:
                results.append({"match_id": mid, "ok": False, "error": str(exc)})
    return results


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
