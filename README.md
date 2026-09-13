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

## Status

Done:
- Data model + initial migration, verified against a live Postgres
  (constraints, cascades, and both migration directions all tested for
  real, not just compiled).
- Spotify OAuth (`/auth/spotify/login`, `/auth/spotify/callback`) with
  encrypted token storage and CSRF-protected state.
- `/me/now-playing` — fetches the current track from Spotify, lazily
  caching the artist/album/track. Verified end-to-end with Spotify
  mocked (respx) against the real schema — this caught a real bug
  (building the response after `db.commit()` tripped SQLAlchemy's
  `expire_on_commit`), since fixed.
- Not yet verified against the *real* Spotify API (needs a Spotify
  Developer app — see setup above).

Next steps:
1. Sync job for top artists/genres/tracks → populates
   `listening_snapshots`.
2. Ratings/reviews/comments/follows/feed endpoints (the `interactions`
   table already models these).
3. Recommendation module + Gemini integration.
4. Frontend.
