# Mon Petit Prono — API reference (reverse-engineered)

Unofficial notes on the `api.mpp.football` REST API, reconstructed from the
public Expo web bundle and verified against live traffic where noted. This is
**not** official documentation and may break at any time.

Confidence legend: ✅ verified live · 🟡 path seen + called OK, shape partial ·
⚪ path only (from bundle), not exercised.

## Base URLs

| Purpose | URL |
|---|---|
| API | `https://api.mpp.football` |
| Auth (Auth0, Ligue 1 SSO) | `https://connect.ligue1.fr` |
| Sibling product (MPG fantasy) | `https://api.mpg.football` |
| Chat service | `https://chat.api.mpg.football` |

The web/mobile apps are built with **Expo / React Native**; the web build and
the native apps all talk to the same backend.

## Authentication ✅

OAuth2 **Authorization Code + PKCE** against Auth0, then a Bearer JWT on the API.

| | |
|---|---|
| Issuer / Auth0 domain | `https://connect.ligue1.fr/` |
| Token endpoint | `POST https://connect.ligue1.fr/oauth/token` |
| Authorize endpoint | `https://connect.ligue1.fr/authorize` |
| `client_id` | `grX5jWGWWQ4Uq91oe7KPNDZ96FS3jr0X` (public SPA client, PKCE, no secret) |
| API audience | `https://mpp.ligue1.fr` |
| Scopes | `openid profile email offline_access` |

API requests carry `Authorization: Bearer <access_token>`. The access token
is a JWT (~2.1 KB, `aud = https://mpp.ligue1.fr`) valid ~24 h.

### Refresh-token grant (how this project authenticates)

```http
POST https://connect.ligue1.fr/oauth/token
Content-Type: application/json

{
  "grant_type": "refresh_token",
  "client_id": "grX5jWGWWQ4Uq91oe7KPNDZ96FS3jr0X",
  "refresh_token": "<your refresh token>"
}
```
Response: `{ "access_token", "expires_in", "token_type": "Bearer", "refresh_token"? }`.

**Refresh-token rotation is ON**: each call returns a *new* `refresh_token` and
invalidates the previous one, so the new value must be persisted. This project
caches it in `.mpp_tokens.json`. Because the browser session and a script share
one token lineage, Auth0 reuse-detection may log one side out if both refresh
with the same token — see the README's caveat.

## Endpoints

### Leagues / contests
- ✅ `GET /user-contests` — your leagues, challenges and pending invitations.
  Top-level keys: `contestsCards[]`, `pinnedChallengesCards[]`,
  `pendingContestsInvitationsCards[]`, `hasNewContestMessages`.
  Each `contestsCards` item: `contestId` (`mpp_challenge_XXXXXXXX`), `title`,
  `championshipId`, `season`, `userRanking`, `userTotalPoints`, `totalUsers`,
  `firstGameWeekNumber`, `lastGameWeekNumber`, `totalGameWeekNumber`, `isLive`.

### Calendar / matches
- 🟡 `GET /championships-current-matches` — dict keyed by `matchId` for the
  featured championships (often the most recent / finished game week). Each:
  `championshipId`, `gameWeekNumber`, `date`, `period` (`fullTime`,
  `abandoned`, …), `quotations {home,draw,away}`, `stats.bets {home,draw,away}`,
  `home`/`away` `{clubId, score, rank, seasonResults[]}`.
- ✅ `GET /championship-calendar/{championshipId}` — `gameWeeks` keyed by number;
  each game week: `gameWeekNumber`, `matchesIds[]`, `startDate`, `endDate`,
  `roundType` (`round`, `roundOf32`, `roundOf16`, `quarterFinals`, …),
  `startIn` (seconds until kickoff, current GW only).
- ✅ `GET /championship-calendar/{championshipId}/next-game-weeks` —
  `{ nextGameWeeks: [ {gameWeekNumber, startDate, endDate, startIn, matchesIds[]}, … ] }`.
- 🟡 `GET /championship-calendar/{championshipId}/nearest-game-weeks` —
  `{ nearestGameWeeks: { nextGameWeek: {...}, … } }`.
- ✅ `GET /championship-match/{matchId}` — match detail. Keys: `id`,
  `championshipId`, `season`, `gameWeekNumber`, `date`, `quotations`, `stats`,
  `areVideosAvailable`, `needLiveRating`, `eventsTimeline`, `home`, `away`.

### Forecasts (predictions) ⭐
- ✅ **Submit / edit a prediction**
  ```http
  PATCH /user-match-forecasts/entity/{scope}/match/{matchId}
  Authorization: Bearer <access_token>
  Content-Type: application/json

  { "homeScore": 1, "awayScore": 1, "originPage": "home" }
  ```
  Response `200`:
  ```json
  { "general": { "homeScore": 1, "awayScore": 1,
    "editedAt": "2026-05-31T15:31:48.245Z",
    "points": { "base": 0, "exact": 0, "extra": 0, "bonus": 0, "total": 0 } } }
  ```
  - Method is **PATCH** and idempotent — re-send to change a prediction before
    kickoff.
  - `{scope}` = `general` is your universal forecast. In MPP you predict a match
    **once** and it counts in every league you're in.
  - `{matchId}` format: `mpp_championship_match_<numericId>`.
  - `originPage` is analytics context and appears optional.
- 🟡 `GET /user-match-forecasts/entity/{scope}/match/{matchId}` — read your
  current prediction (same path).

### Other endpoints seen in the bundle (⚪ not exercised here)
`/general-standings/top-users-standings`, `/challenge-standings/top-users-standings`,
`/championship-standings/{id}`, `/user-bonuses/match/{matchId}`,
`/championship-clubs`, `/championship-club/lfp/{id}`,
`/championship-players-ranking/{championshipId}/{goals|assists|ratings}`,
`/badges`, `/user-notifications`, plus the chat service on
`chat.api.mpg.football`. Contributions welcome to verify and document these.
