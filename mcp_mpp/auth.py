"""Auth0 refresh-token auth for Mon Petit Prono.

The MPP web/mobile app authenticates against Ligue 1's Auth0 tenant
(`connect.ligue1.fr`) using OAuth2 Authorization Code + PKCE. The resulting
access token (JWT, audience `https://mpp.ligue1.fr`) is sent as
`Authorization: Bearer ...` to `api.mpp.football`.

We don't replay the interactive login. Instead we seed a long-lived
**refresh token** once (extracted from the logged-in browser, see .env.example)
and exchange it for fresh access tokens via the Auth0 token endpoint.

Refresh-token rotation: if the tenant rotates refresh tokens, each exchange
returns a new `refresh_token` that invalidates the previous one. We persist
whatever we get back into `.mpp_tokens.json` so the seed in .env is only ever
used on the very first run.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

AUTH0_DOMAIN = os.environ.get("MPP_AUTH0_DOMAIN", "https://connect.ligue1.fr").rstrip("/")
CLIENT_ID = os.environ.get("MPP_AUTH0_CLIENT_ID", "grX5jWGWWQ4Uq91oe7KPNDZ96FS3jr0X")
AUDIENCE = os.environ.get("MPP_AUTH0_AUDIENCE", "https://mpp.ligue1.fr")
TOKEN_URL = f"{AUTH0_DOMAIN}/oauth/token"

# Token cache lives next to the project root, gitignored.
TOKEN_STORE = Path(os.environ.get("MPP_TOKEN_STORE", ".mpp_tokens.json")).resolve()

# Refresh this many seconds before the access token actually expires.
EXPIRY_SKEW = 90


class AuthError(RuntimeError):
    pass


class TokenStore:
    """Holds the current refresh token + cached access token, persisted to disk."""

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.expires_at: float = 0.0
        self.refresh_token: str | None = None
        self._load()

    def _load(self) -> None:
        if TOKEN_STORE.exists():
            try:
                data = json.loads(TOKEN_STORE.read_text(encoding="utf-8"))
                self.access_token = data.get("access_token")
                self.expires_at = float(data.get("expires_at", 0))
                self.refresh_token = data.get("refresh_token")
            except (ValueError, OSError):
                pass
        # Seed the refresh token from the environment on first run only.
        if not self.refresh_token:
            self.refresh_token = os.environ.get("MPP_REFRESH_TOKEN") or None

    def _save(self) -> None:
        TOKEN_STORE.write_text(
            json.dumps(
                {
                    "access_token": self.access_token,
                    "expires_at": self.expires_at,
                    "refresh_token": self.refresh_token,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        # Best-effort: keep the secret file readable only by the owner.
        try:
            os.chmod(TOKEN_STORE, 0o600)
        except OSError:
            pass

    def access_token_valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and self.access_token_valid():
            return self.access_token  # type: ignore[return-value]
        return self._refresh()

    def _refresh(self) -> str:
        if not self.refresh_token:
            raise AuthError(
                "No refresh token. Set MPP_REFRESH_TOKEN in .env (see .env.example) "
                "by extracting it from the logged-in MPP web app."
            )
        payload = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": self.refresh_token,
        }
        try:
            resp = httpx.post(TOKEN_URL, json=payload, timeout=20)
        except httpx.HTTPError as exc:  # network-level
            raise AuthError(f"Token endpoint unreachable: {exc}") from exc

        if resp.status_code != 200:
            # Don't leak the token; surface Auth0's error code only.
            detail = ""
            try:
                detail = resp.json().get("error", "")
            except ValueError:
                detail = resp.text[:200]
            raise AuthError(
                f"Refresh failed ({resp.status_code}: {detail}). "
                "The refresh token may be expired/revoked — re-seed MPP_REFRESH_TOKEN."
            )

        data = resp.json()
        self.access_token = data["access_token"]
        self.expires_at = time.time() + int(data.get("expires_in", 3600)) - EXPIRY_SKEW
        # Rotation: persist the new refresh token if Auth0 issued one.
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        self._save()
        return self.access_token  # type: ignore[return-value]


# Module-level singleton so every caller shares one cached token.
_store = TokenStore()


def get_access_token(*, force_refresh: bool = False) -> str:
    return _store.get_access_token(force_refresh=force_refresh)


def _cli() -> None:
    """`python -m mcp_mpp.auth` — verify the refresh flow WITHOUT printing the token."""
    try:
        token = get_access_token(force_refresh=True)
    except AuthError as exc:
        print(f"AUTH FAIL: {exc}")
        raise SystemExit(1)
    remaining = int(_store.expires_at - time.time())
    rotated = bool(os.environ.get("MPP_REFRESH_TOKEN")) and (
        _store.refresh_token != os.environ.get("MPP_REFRESH_TOKEN")
    )
    print("AUTH OK")
    print(f"  access token acquired: {len(token)} chars (not shown)")
    print(f"  expires in ~{remaining}s")
    print(f"  refresh-token rotation: {'ON (new token persisted)' if rotated else 'off / unchanged'}")
    print(f"  token store: {TOKEN_STORE}")


if __name__ == "__main__":
    _cli()
