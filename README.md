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
  auth/            Spotify OAuth login + our own JWT session
  spotify_sync/    Pull + cache top artists/tracks/genres, currently playing
  social/          Ratings, reviews, comments, likes, follows, feed
  recommendations/ Taste breakdown + LLM-generated summary & suggestions
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

## Status

Scaffolding only — no models, endpoints, or frontend yet. Next steps:
1. Define the data model (`users`, `artists`, `albums`, `tracks`,
   `ratings`, `reviews`, `comments`, `likes`, `follows`,
   `listening_snapshots`) as SQLAlchemy models, then generate the first
   Alembic migration.
2. Spotify OAuth flow (`/auth/spotify/login`, `/auth/spotify/callback`).
3. Sync job for top artists/genres/tracks.
4. Ratings/reviews/comments/follows endpoints.
5. Recommendation module + Gemini integration.
6. Frontend.
