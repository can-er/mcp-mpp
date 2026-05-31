"""Thin typed client over the Mon Petit Prono REST API (`api.mpp.football`).

Endpoint paths were reverse-engineered from the Expo web bundle. The prediction
write (PATCH) is verified against live traffic. See `docs/API.md` for the full
contract and confidence level of each endpoint.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .auth import AuthError, get_access_token

API_BASE = os.environ.get("MPP_API_BASE", "https://api.mpp.football").rstrip("/")

# Mimic the real web client closely enough to avoid header-based gating.
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://mpp.football",
    "Referer": "https://mpp.football/",
    "User-Agent": "mcp-mpp/0.1 (unofficial; personal automation)",
}


class MppApiError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"MPP API {status}: {body[:300]}")
        self.status = status
        self.body = body


class MppClient:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self._http = httpx.Client(base_url=API_BASE, timeout=timeout, headers=_DEFAULT_HEADERS)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "MppClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ---------------------------------------------------------
    def _auth_headers(self, *, force_refresh: bool = False) -> dict[str, str]:
        return {"Authorization": f"Bearer {get_access_token(force_refresh=force_refresh)}"}

    def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        resp = self._http.request(method, path, headers=self._auth_headers(), json=json)
        # One automatic retry with a forced token refresh on 401.
        if resp.status_code == 401:
            resp = self._http.request(
                method, path, headers=self._auth_headers(force_refresh=True), json=json
            )
        if resp.status_code >= 400:
            raise MppApiError(resp.status_code, resp.text)
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # -- leagues / contests ------------------------------------------------
    def contests(self) -> Any:
        """Raw `/user-contests` payload (leagues, challenges, invitations)."""
        return self._request("GET", "/user-contests")

    def my_leagues(self) -> list[dict[str, Any]]:
        """Flattened view of the leagues/challenges the account belongs to."""
        data = self.contests()
        cards = (data or {}).get("contestsCards", []) if isinstance(data, dict) else []
        out: list[dict[str, Any]] = []
        for c in cards:
            if not isinstance(c, dict):
                continue
            out.append(
                {
                    "contest_id": c.get("contestId"),
                    "title": c.get("title"),
                    "championship_id": c.get("championshipId"),
                    "season": c.get("season"),
                    "ranking": c.get("userRanking"),
                    "points": c.get("userTotalPoints"),
                    "total_users": c.get("totalUsers"),
                    "first_game_week": c.get("firstGameWeekNumber"),
                    "last_game_week": c.get("lastGameWeekNumber"),
                }
            )
        return out

    # -- calendar / matches ------------------------------------------------
    def current_matches(self) -> Any:
        """Matches of the currently featured championships (often recent/finished)."""
        return self._request("GET", "/championships-current-matches")

    def championship_calendar(self, championship_id: int | str) -> Any:
        """Full calendar of a championship: game weeks -> matchesIds + dates."""
        return self._request("GET", f"/championship-calendar/{championship_id}")

    def next_game_weeks(self, championship_id: int | str) -> Any:
        return self._request("GET", f"/championship-calendar/{championship_id}/next-game-weeks")

    def nearest_game_weeks(self, championship_id: int | str) -> Any:
        return self._request(
            "GET", f"/championship-calendar/{championship_id}/nearest-game-weeks"
        )

    def match(self, match_id: str) -> Any:
        """Match detail (teams/clubIds, kickoff date, odds, stats)."""
        return self._request("GET", f"/championship-match/{match_id}")

    # -- forecasts ---------------------------------------------------------
    def my_forecast(self, match_id: str, *, scope: str = "general") -> Any:
        return self._request(
            "GET", f"/user-match-forecasts/entity/{scope}/match/{match_id}"
        )

    def submit_forecast(
        self,
        match_id: str,
        home_score: int,
        away_score: int,
        *,
        scope: str = "general",
        origin_page: str | None = "home",
    ) -> Any:
        """Submit (or edit) a score prediction for a match.

        VERIFIED contract:
            PATCH /user-match-forecasts/entity/{scope}/match/{match_id}
            { "homeScore": int, "awayScore": int, "originPage": str }
        Idempotent — re-PATCH to change the prediction before kickoff. `scope`
        "general" is your universal forecast, counted across all your leagues.
        """
        if home_score < 0 or away_score < 0:
            raise ValueError("scores must be >= 0")
        body: dict[str, Any] = {"homeScore": int(home_score), "awayScore": int(away_score)}
        if origin_page is not None:
            body["originPage"] = origin_page
        return self._request(
            "PATCH", f"/user-match-forecasts/entity/{scope}/match/{match_id}", json=body
        )


__all__ = ["MppClient", "MppApiError", "AuthError"]
