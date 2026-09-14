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
  api/               auth.py (Spotify OAuth + logout), deps.py (current-user dependency),
                      catalog.py (public search/album lookup), playback.py (now-playing,
                      top-tracks/albums/artists), interactions.py (reviews/comments/likes),
                      users.py (GET /me profile)
  services/          spotify.py (raw API client), token_service.py (refresh),
                      spotify_sync.py (Spotify JSON -> cached rows), interactions.py
  security.py        Fernet token encryption, session JWT, signed OAuth state
  models/            SQLAlchemy models (see Data model below)

frontend/            React (Vite + TypeScript). src/pages: Home (landing when logged
                     out, dashboard cards when logged in), Search, AlbumDetail
                     (tracklist + reviews/comments/likes). src/context/AuthContext
                     checks GET /me on load. Talks to the backend via fetch with
                     credentials: "include" (cookie-based session).
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

### Google OAuth setup

Google login has no user cap (unlike Spotify's Development Mode) — it's
the account system for everyone who isn't one of the few Spotify
testers. Setup:

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs &
   Services → Credentials → Create OAuth client ID → Web application.
2. Add `http://127.0.0.1:8000/auth/google/callback` as an Authorized
   redirect URI.
3. Put the Client ID/Secret into `backend/.env`
   (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).

No scope beyond basic profile/email is requested — we never call
Google's API again after login, unlike Spotify where the token is kept
for ongoing personalized data.

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173` — **not `localhost:5173`**, for the same
reason as above. The backend's CORS config (`FRONTEND_ORIGIN` in
`.env`) and cookie handling both assume `127.0.0.1` throughout.

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

## What Spotify's API won't give us (verified live, not assumed)

Three real gaps found by actually testing against Spotify, each with a
workaround already built rather than just documented:

1. **No global charts.** `/browse/new-releases`, `/browse/featured-playlists`,
   `/browse/categories`, even their own "Top 50 - Global" playlist ID —
   all 403/404 for new developer apps (locked behind "Extended Quota
   Mode" since late 2024). Workaround: `/me/top-tracks`/`/me/top-artists`
   give a personalized card UI from the logged-in user's own data
   instead — arguably better anyway — and `/hot-albums` (most-reviewed,
   from our own `interactions` table) covers "something to look at
   before logging in."
2. **No annual listening time.** There's no "total minutes this year"
   endpoint at all — that's Wrapped-exclusive, computed from data
   Spotify never exposes to third-party apps. Workaround:
   `/me/taste-summary`'s `recent_minutes_listened` is a real number
   derived from the last ~50 plays (`get_recently_played`), honestly
   labeled in the UI as a recent estimate, not a year total.
3. **No artist genre tags, at all.** Verified directly against
   `GET /artists/{id}` for Charli xcx (a hugely mainstream artist):
   `genres: null`. Checked every one of the 94 real artists cached in
   the database at the time: zero had any genre tag. Workaround:
   Gemini classifies artist names into genres using its own knowledge
   (`app/services/genre_classification.py`), cached onto the `Artist`
   row itself so it's a one-time cost per artist shared across every
   user, not a per-request LLM call.

## Status

Done:
- Data model + migrations, verified against a live Postgres (constraints,
  cascades/restricts, and both migration directions all tested for real,
  not just compiled).
- Spotify OAuth (`/auth/spotify/login`, `/auth/spotify/callback`) with
  encrypted token storage and CSRF-protected state.
- Google OAuth (`/auth/google/login`, `/auth/google/callback`) — a
  second, independent way to get an account, since Spotify's own login
  is capped at 5 users in Development Mode. `users.spotify_id`/`google_id`
  are both nullable with a `CHECK (num_nonnulls >= 1)` — an account
  needs at least one identity, and a Google-only account can later
  connect Spotify onto the *same* row rather than ending up split
  across two accounts (verified: logging in with Google using an email
  that matches an existing Spotify account links onto it). Personalized
  endpoints (`/me/now-playing`, `/me/top-*`) 403 with a clear message
  for accounts with no Spotify connected, via a global exception
  handler (`SpotifyNotConnected` in `app/services/token_service.py`) —
  verified the dashboard handles this gracefully in the browser rather
  than showing a raw error.
- `/me/now-playing`, `/me/top-tracks`, `/me/top-artists` — fetch from
  Spotify and lazily cache the artist/album/track. Verified with Spotify
  mocked (respx) against the real schema.
- `/catalog/albums/search`, `/catalog/albums/{spotify_id}` — public
  catalog search/lookup (Client Credentials flow, no login needed).
  Verified against the *real* Spotify API (searched "Madonna Ray of
  Light", fetched the full 13-track album, confirmed correct FK linkage
  in Postgres).
- Real login verified live: real Spotify account, real user row created,
  real encrypted tokens.
- `POST /auth/spotify/logout` — clears the session cookie. It's a
  stateless signed JWT with no server-side session record, so this
  can't revoke the token itself, only tell the browser to forget it;
  a copied token would still verify until its 60-minute expiry.
  Accepted trade-off, not an oversight.
- **Frontend** (`frontend/`, React + Vite + TypeScript): landing page,
  a dashboard of your top albums/tracks/artists as cards, search with
  debounced type-ahead, and an album page with tracklist + reviews/
  comments/likes. Verified live in a real (headless) browser against
  the real backend and a real Spotify account — not just "it compiles":
  confirmed CORS works cross-origin, confirmed the actual card UI
  renders with real cover art/data, confirmed posting a review through
  the real form works. This is how a real bug got caught: every "top
  artist" card was showing a blank placeholder image instead of the
  artist's photo (see below).
- `POST /albums/{spotify_id}/reviews`, `GET /albums/{spotify_id}/reviews`,
  `POST /reviews/{id}/comments`, `POST /reviews/{id}/like`,
  `POST /comments/{id}/like` — the actual rate/review/comment/like
  endpoints on top of `interactions`. Verified both with mocked-Spotify
  tests AND live against the real API/DB (posted a real 5-star review
  on *Ray of Light* from the real logged-in account, confirmed the
  duplicate-review and duplicate-like constraints both reject correctly
  with 409s).
- `/me/top-albums` — derived from top tracks (deduped by album), since
  Spotify has no direct "top albums" endpoint.

Two real bugs the tests caught, worth knowing about since they're easy
to reintroduce elsewhere:
1. **Test/prod session config mismatch, not a code bug per se**: the app's
   real session factory (`app/db.py`) already sets `expire_on_commit=False`,
   but the test fixture didn't match it, so tests were enforcing stricter
   behavior than production actually has. Fixed by aligning them
   (`tests/conftest.py`).
2. **Enum serialization**: SQLAlchemy's `Enum` type persists a Python enum
   member's *name* ("REVIEW") by default, not its *value* ("review") —
   silently mismatching the lowercase values the Postgres enum type
   actually has, unless `values_callable` is set. Hit on `Interaction.type`
   (would have failed on literally every insert); pre-emptively fixed the
   same latent bug on `ListeningSnapshot.time_range` too, since it hadn't
   been exercised by any code yet but had the identical pattern.
3. **Artist enrichment gap, caught visually in the browser check**:
   `_get_or_create_artist` only set genres/images when *creating* a row.
   An artist first cached from a partial stub (id/name only — what
   now-playing/top-tracks/album tracklists give) stayed permanently
   incomplete even after a richer source (top-artists) saw the same
   artist later, because the "already exists" branch just returned it
   as-is. Every card in "Your top artists" showed a blank placeholder
   image until this was fixed to enrich in place
   (`tests/test_spotify_sync_enrichment.py`).

Known, deliberate gap: nothing currently stops liking your own review —
worth a product decision on whether that should be blocked.

- **`/me/taste-summary`, `/me/recommendations`, and the `/taste` page**
  (`google-genai` SDK, `gemini-3.8-flash`): genre pie chart (fed by
  Gemini-classified genres, see above — the chart legitimately shows
  "not enough genre data" when `GEMINI_API_KEY` isn't set, which is the
  honest behavior, not a bug), a recent-listening estimate, and a
  one-shot (no chat) AI taste summary + adjacent genre/artist
  recommendations behind a "Generate" button. `/me/recommendations`
  gracefully returns `{"available": false}` without an API key rather
  than erroring — verified both paths live in the browser (screenshot
  before/after), including the real structured-JSON parsing from a
  mocked Gemini response in tests.
- Fixed a real dependency conflict installing `google-genai`: it
  requires `httpx>=0.28.1`, which silently upgraded httpx and broke
  `respx`'s mocking across the *entire* test suite (15 unrelated tests
  failed) until `respx` was upgraded to `0.23.1` too. Worth knowing:
  installing an unrelated package can break testing infrastructure via
  a shared transitive dependency.

Next steps:
1. Cache-retention job (see above) — blocked on picking a hosting/
   scheduling approach.
2. Multi-type (track/artist/album) search for type-ahead.
3. Extend reviews/comments/likes to artists and tracks, not just albums
   (currently album-only).
