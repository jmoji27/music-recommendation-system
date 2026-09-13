# Music Recommendation System

A Letterboxd-inspired app for music: sync your Spotify listening stats,
rate and review artists/albums/tracks, follow other users, and get an
LLM-generated summary of your taste plus personalized recommendations.

## Architecture

Modular monolith backend (FastAPI) — one service, cleanly separated modules,
so it's simple to run and deploy solo but easy to peel a module into its own
service later if needed.

```
backend/app/
  api/               auth.py (Spotify OAuth), deps.py (current-user dependency),
                      playback.py (now-playing) — social/recommendations routes land here next
  services/          spotify.py (raw API client), token_service.py (refresh),
                      spotify_sync.py (Spotify JSON -> cached rows)
  security.py        Fernet token encryption, session JWT, signed OAuth state
  models/            SQLAlchemy models (see Data model below)
```

- **Database:** PostgreSQL (relational — the social graph and ratings/reviews
  have real referential-integrity needs). SQLAlchemy (async) + Alembic
  migrations.
- **Auth:** Spotify OAuth is the only login method — you need Spotify
  connected for the app to be useful anyway, so there's no separate
  password system to secure.
- **Feed:** fan-out-on-read (compute a followed user's recent activity at
  request time) rather than fan-out-on-write. Simple and correct at
  portfolio scale; revisit with a queue + precomputed feeds if this ever
  needs to scale.
- **LLM:** Google Gemini (Flash tier, free quota) called directly via
  Google's SDK — no LangChain for now, since there's one provider and a
  couple of well-defined prompts (taste summary, recommendations).
- **Frontend:** React (Vite) first, React Native later, both consuming the
  same FastAPI backend (OpenAPI schema auto-generated at `/docs`).

## Security notes

- Spotify client secret, Gemini API key, and JWT secret live only in the
  backend's `.env`, never in frontend code.
- Spotify refresh tokens are stored encrypted at rest.
- All review/comment text is sanitized before storage/render (stored XSS
  is the main risk on any UGC feature).
- Outbound Spotify calls are cached — top artists/genres don't need to be
  refetched on every page load.

## Local dev setup

```bash
# 1. Start Postgres
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in Spotify + Gemini credentials
alembic upgrade head   # once there are migrations
uvicorn app.main:app --reload

# 3. Check it's alive
curl http://localhost:8000/health
```

### Spotify OAuth setup

1. Create an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Add `http://127.0.0.1:8000/auth/spotify/callback` as a Redirect URI —
   **not** `localhost`. Spotify rejects `localhost` outright now; only an
   explicit loopback IP literal (`127.0.0.1` or `[::1]`) is accepted for
   local dev.
3. Put the Client ID/Secret into `backend/.env`
   (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`).
4. **Always use `http://127.0.0.1:8000/...` in the browser, not
   `localhost:8000`**, once you're testing the OAuth flow — the CSRF
   protection on `/auth/spotify/callback` uses a same-origin cookie set
   during `/auth/spotify/login`, and browsers treat `localhost` and
   `127.0.0.1` as different origins, so mixing them breaks the cookie
   check.

## Data model

Implemented in `backend/app/models/` with an initial Alembic migration
(`backend/alembic/versions/c0b6e28d1d3b_initial_schema.py`):
`users`, `artists`, `albums`, `tracks`, `interactions`, `follows`,
`listening_snapshots`.

`artists`/`albums`/`tracks` are a local cache keyed by Spotify's own IDs,
populated **on demand** — an artist is only fetched from Spotify and
upserted here the first time a user looks it up, not bulk-synced ahead of
time. Trade-off: searching for an artist nobody's looked up yet has to
hit Spotify's search API live rather than querying the local DB.

`interactions` is a single table for ratings/reviews, comments, and
likes, discriminated by `type`:
- `type='review'` — a top-level log entry. Targets exactly one of
  `artist_id`/`album_id`/`track_id` (exclusive arc: nullable FK columns +
  a `CHECK (num_nonnulls(...) = 1)` constraint, instead of a generic
  `entity_type`/`entity_id` pair — keeps real referential integrity).
  Has `stars` and/or `content` (you can just log a rating, or write about
  it too).
- `type IN ('comment', 'like')` — a reply. Targets `parent_interaction_id`
  (another row in the same table — the review, or a comment for a like)
  instead of the music entity directly, matching how Letterboxd actually
  works: you comment on/like someone's specific review, not the album
  page itself. `comment` requires `content`; `like` has none.

Collapsing reviews/comments/likes into one table means a feed query is a
single scan (`interactions` ordered by `created_at`, filtered to people
you follow) instead of a `UNION` across three tables.

The migration was hand-written and verified with `alembic upgrade head
--sql` / `alembic downgrade base --sql` (offline mode, no live DB
required) rather than autogenerated, since there's no Postgres instance in
the environment it was built in. Run it for real against your local
Postgres with `alembic upgrade head` once `docker compose up -d` is
running.

## Cache retention (planned)

Cached artists/albums/tracks with zero interactions after 6 months are
meant to be deleted by a scheduled job (not built yet — needs a hosting
decision first, since it needs to run on a schedule independent of
whether the web process is awake). The schema is already safe for this:
`cached_at` columns (added in the second migration) give the job a
reference point, and `interactions.artist_id`/`album_id`/`track_id` use
`ON DELETE RESTRICT` rather than `CASCADE` — if the job's "zero
interactions" check is ever wrong, Postgres refuses the delete with an
error instead of silently destroying a real review/comment/like. "Zero
interactions" means zero of *any* interaction type (review, comment, or
like) — a plain star rating with no written text still counts.

## No global charts — Spotify doesn't allow it for new apps

Originally planned: seed the catalog with a monthly top-100
songs/albums sync so new users see something browsable instead of an
empty search box. Tested live against Spotify with real credentials —
`/browse/new-releases`, `/browse/featured-playlists`, `/browse/categories`,
and even Spotify's own "Top 50 - Global" playlist ID all return
403/404. Spotify locked these behind "Extended Quota Mode" for new
developer apps in late 2024; it's not something this app can fix.

Instead: `/me/top-tracks` and `/me/top-artists` (below) populate an
interactive card UI from the *logged-in user's own* Spotify data right
after login — no global chart needed, and arguably better UX since it's
personalized from the start.

## Status

Done:
- Data model + migrations, verified against a live Postgres (constraints,
  cascades/restricts, and both migration directions all tested for real,
  not just compiled).
- Spotify OAuth (`/auth/spotify/login`, `/auth/spotify/callback`) with
  encrypted token storage and CSRF-protected state.
- `/me/now-playing`, `/me/top-tracks`, `/me/top-artists` — fetch from
  Spotify and lazily cache the artist/album/track. Verified with Spotify
  mocked (respx) against the real schema.
- `/catalog/albums/search`, `/catalog/albums/{spotify_id}` — public
  catalog search/lookup (Client Credentials flow, no login needed).
  Verified against the *real* Spotify API (searched "Madonna Ray of
  Light", fetched the full 13-track album, confirmed correct FK linkage
  in Postgres).
- `/me/now-playing`/`/me/top-*` are NOT yet verified against the real
  API — that needs an actual browser login (Spotify's consent screen
  can't be automated), which you can try yourself now that real
  credentials are in `.env`: visit
  `http://127.0.0.1:8000/auth/spotify/login`.

Next steps:
1. Cache-retention job (see above) — blocked on picking a hosting/
   scheduling approach.
2. Multi-type (track/artist/album) search for type-ahead, and wiring
   search into the `interactions` table so users can actually
   rate/review something they searched for.
3. Ratings/reviews/comments/follows/feed endpoints (the `interactions`
   table already models these).
4. Recommendation module + Gemini integration.
5. Frontend.
