# mcp-mpp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP server](https://img.shields.io/badge/MCP-server-1f6feb?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![Managed with uv](https://img.shields.io/badge/managed%20with-uv-de5fe9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Status: unofficial](https://img.shields.io/badge/status-unofficial-orange.svg)](#)
[![Last commit](https://img.shields.io/github/last-commit/can-er/mcp-mpp)](https://github.com/can-er/mcp-mpp/commits/main)

An **MCP server for [Mon Petit Prono](https://mpp.football)** (MPP) — the French
football-prediction game. It lets an AI assistant (Claude, or any MCP client)
read your open matches and **submit your score predictions** programmatically,
so you can automate your picks for your leagues with friends.

You connect it to your **own** MPP account with your **own** token. Every user
runs it for themselves.

> [!WARNING]
> **Unofficial project.** Not affiliated with, endorsed by, or supported by Mon
> Petit Prono, Mon Petit Gazon (MPG), or Ligue 1. It talks to an undocumented,
> private API that can change or break at any time, and automating the game may
> be against its Terms of Service. Use it on your own account, at your own risk.
> No warranty (see [LICENSE](./LICENSE)).

---

## What it can do

| MCP tool | Description |
|---|---|
| `list_my_leagues` | Your leagues/challenges with ranking, points and their `championship_id` |
| `championship_calendar(championship_id)` | Full calendar: game weeks → match ids + dates |
| `upcoming_game_weeks(championship_id)` | Next game weeks with their match ids |
| `get_match(match_id)` | Match detail: teams, kickoff, odds, stats |
| `get_my_forecast(match_id)` | Your current prediction for a match |
| `submit_forecast(match_id, home_score, away_score)` | Submit/edit one prediction |
| `submit_forecasts([...])` | Submit several at once |

Predictions are submitted with a single idempotent `PATCH` — re-running simply
updates the prediction (allowed until kickoff).

---

## Requirements

- [Python ≥ 3.11](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or see their docs)
- An MPP account you can log into at <https://mpp.football>

## Install

```bash
git clone https://github.com/can-er/mcp-mpp.git
cd mcp-mpp
uv sync
```

## Authentication — get your token

MPP uses **Auth0 single sign-on** (Ligue 1 SSO). There is no API key. Instead,
the app holds a short-lived **access token** (~24 h) and a long-lived
**refresh token**. This server uses your refresh token to mint fresh access
tokens automatically — no password is ever stored or sent.

You seed your refresh token **once**:

1. Log in to <https://mpp.football> in your browser.
2. Open **DevTools → Console** (F12) and run this — it copies your refresh token
   to the clipboard without displaying it:
   ```js
   copy(Object.values(localStorage)
     .map(v => { try { return JSON.parse(v) } catch { return null } })
     .find(o => o && o.body && o.body.refresh_token).body.refresh_token)
   ```
3. Create your `.env` and paste the value:
   ```bash
   cp .env.example .env       # Windows: copy .env.example .env
   ```
   Open `.env` and set `MPP_REFRESH_TOKEN=<paste here>`.
4. Verify it works (prints OK + expiry, **never the token itself**):
   ```bash
   uv run python -m mcp_mpp.auth
   ```

### How the tokens work

- **Access token** — JWT sent as `Authorization: Bearer …` to `api.mpp.football`,
  valid ~24 h. The server caches it and only refreshes when it nears expiry.
- **Refresh token** — long-lived; exchanged at `connect.ligue1.fr/oauth/token`
  for new access tokens. It is cached in `.mpp_tokens.json` (gitignored).
- **Rotation** — MPP's Auth0 tenant rotates refresh tokens: each refresh returns
  a *new* refresh token and invalidates the old one. The server persists the new
  one automatically, so the value in `.env` is only the first-run seed.

> [!NOTE]
> Because your browser session and this server share one token lineage, Auth0's
> reuse-detection can log one side out if both refresh with the same token. In
> practice this is rare for occasional use (the access token lasts ~24 h). If you
> ever get logged out or auth starts failing, just repeat the steps above to
> re-seed `MPP_REFRESH_TOKEN` (delete `.mpp_tokens.json` first).

## Run

```bash
uv run mcp-mpp            # start the MCP server (stdio)
```

Quick non-MCP checks:

```bash
uv run python -m mcp_mpp.auth      # verify auth
uv run python -m mcp_mpp.probe 8   # smoke-test reads for championship 8
```

## Use it with Claude

Register the server with your MCP client. For Claude Desktop / Claude Code,
add to your MCP config (adjust the path):

```json
{
  "mcpServers": {
    "mpp": {
      "command": "uv",
      "args": ["run", "mcp-mpp"],
      "cwd": "/absolute/path/to/mcp-mpp"
    }
  }
}
```

Then ask, for example: *"List my MPP leagues, show the next game week's matches,
and predict sensible scores for each."*

## How it works

```
your MPP account                          this project
─────────────────                         ─────────────
browser login (Auth0)  ──► refresh token ──► auth.py  ──► access token
                                              client.py ──► api.mpp.football
                                              server.py ──► MCP tools ──► Claude
```

See [`docs/API.md`](./docs/API.md) for the reverse-engineered API reference and
[`CLAUDE.md`](./CLAUDE.md) for architecture/contributor notes.

## Project layout

```
mcp-mpp/
├── mcp_mpp/
│   ├── auth.py      # Auth0 refresh-token flow (+ rotation, disk cache)
│   ├── client.py    # typed REST client for api.mpp.football
│   ├── server.py    # MCP server (FastMCP) — the tools above
│   └── probe.py     # read-endpoint smoke test
├── docs/API.md      # reverse-engineered API reference
├── .env.example     # config template (fill in your refresh token)
├── pyproject.toml
└── CLAUDE.md
```

## Security & privacy

- Secrets (`.env`, `.mpp_tokens.json`) are gitignored — **never commit them**.
- Your refresh token grants access to your account: keep it private.
- The server only ever acts on the account whose token you provide.

## Contributing

Issues and PRs welcome — especially verifying the ⚪ endpoints in
[`docs/API.md`](./docs/API.md) (standings, bonuses, club names) and adding tests.
Please never include real tokens or other players' data in issues or commits.

## License

[MIT](./LICENSE)
