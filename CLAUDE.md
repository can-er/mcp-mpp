# CLAUDE.md — contributor & architecture notes

Guidance for Claude Code (and humans) working on this repo. User-facing docs are
in [`README.md`](./README.md); the reverse-engineered API reference is in
[`docs/API.md`](./docs/API.md).

## What this is

An **unofficial MCP server for Mon Petit Prono (MPP)**, the French football
prediction game. It exposes MCP tools to read open matches and submit score
predictions, so an MCP client (e.g. Claude) can automate a user's picks.

Each user runs it against **their own** MPP account with **their own** refresh
token. The server only ever acts on that one account.

> **Scope & ethics.** Single-account, owner-operated automation of a casual game.
> Not a scraper, not multi-account, not a way to touch other users' data.
> - Human-like request volume — reads are cheap; writes are a handful per game week.
> - The API is private/undocumented and automating may breach MPP's ToS; that is
>   the operator's risk and is disclaimed in the README. Don't expand blast radius
>   beyond the running user's own account.
> - Never commit tokens or other players' data; sanitize anything saved under `docs/`.

## Architecture

```
auth.py    Auth0 refresh-token flow → cached access token (.mpp_tokens.json)
client.py  thin typed REST client over api.mpp.football (uses auth.py)
server.py  FastMCP server exposing the MCP tools (uses client.py)
probe.py   dev smoke-test for read endpoints (shapes only, redacted)
```

- **auth.py** — exchanges the refresh token at `connect.ligue1.fr/oauth/token`.
  Refresh-token **rotation is ON**, so the new refresh token is persisted after
  every exchange; `.env`'s `MPP_REFRESH_TOKEN` is only the first-run seed.
- **client.py** — one method per endpoint; raises `MppApiError` on 4xx/5xx and
  auto-retries once with a forced token refresh on 401. The prediction write is
  the verified `PATCH /user-match-forecasts/entity/{scope}/match/{matchId}`.
- **server.py** — write mode is **immediate** (no confirmation); the PATCH is
  idempotent and every write is logged to stderr.

See [`docs/API.md`](./docs/API.md) for endpoints, payloads and per-endpoint
confidence levels. Key facts: API base `https://api.mpp.football`; predictions
use `scope = general` (one prediction per match counts across all your leagues);
match ids look like `mpp_championship_match_<numericId>`; a league's matches live
under its `championshipId` calendar.

## Conventions

- Python ≥ 3.11, managed with `uv`. Deps in `pyproject.toml`; `uv.lock` committed.
- Secrets in `.env` / `.mpp_tokens.json` (both gitignored). Never print a token —
  `auth.py`'s CLI reports length + expiry only; `probe.py` redacts token/PII keys.
- Match the surrounding style: small typed methods, docstrings noting the verified
  HTTP contract, no broad excepts.

## Open questions / next steps
- [ ] Confirm Auth0 refresh-token rotation behaviour vs. the browser session
      (reuse-detection logout) and document a clean re-seed flow.
- [ ] Resolve `clubId` → readable team name (`/championship-clubs`) for nicer output.
- [ ] Verify the ⚪ endpoints in `docs/API.md` (standings, `/user-bonuses/match/{id}`).
- [ ] How are "bonus" picks submitted (separate call vs. part of the forecast)?
- [ ] Optional: add tests and a CI workflow.
