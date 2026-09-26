# Deploying (free tier, free subdomains)

Picks for this setup: **Render** for the backend + Postgres, **Vercel**
for the frontend. Both free, both deploy straight from GitHub.

Because frontend and backend end up on different domains
(`something.onrender.com` / `something.vercel.app`), they're
cross-site, not same-site — that's why the code uses
`SameSite=None; Secure` cookies in production (`app/cookies.py`) instead
of the `Lax` used locally. Known trade-off of this path: some browsers
(Safari, Firefox in strict privacy modes) partially restrict cross-site
cookies even with that setting. Owning a real domain later and routing
both under it removes this class of problem entirely — not needed to
start.

## 0. Push to GitHub

Both Render and Vercel deploy by connecting to a GitHub repo. If this
project isn't on GitHub yet, that has to happen first — ask before
doing this part, since creating/pushing a repo is visible and not
something to do silently.

## 1. Database — Render Postgres (or Supabase/Neon)

Create a free Postgres instance. Note the connection string — you'll
need it as `DATABASE_URL` (SQLAlchemy async needs the `+asyncpg`
dialect prefix: `postgresql+asyncpg://...`, not the plain
`postgresql://...` the host gives you by default).

Run migrations against it once, from your machine, pointed at the
production DB:
```bash
cd backend
DATABASE_URL=<production-url-with-+asyncpg> .venv/bin/alembic upgrade head
```

## 2. Backend — Render Web Service

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
  (behind Render's proxy this makes rate limits see real client IPs)
- Environment variables (Render's dashboard, not `.env` — nothing
  secret is ever committed):
  - `DATABASE_URL` (from step 1)
  - `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`
  - `SPOTIFY_REDIRECT_URI` = `https://<your-render-app>.onrender.com/auth/spotify/callback`
  - `TOKEN_ENCRYPTION_KEY`, `JWT_SECRET` (generate new ones for
    production — don't reuse your local dev values; the app refuses to
    start in production with a weak `JWT_SECRET`)
  - Optional Google login: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
    `GOOGLE_REDIRECT_URI` = `https://<your-render-app>.onrender.com/auth/google/callback`
    (also add it under Authorized redirect URIs in Google Cloud Console)
  - Rate limiting is in-memory per process: keep one worker, or move it
    to Redis before scaling out. API docs (`/docs`) are disabled in production.
  - `FRONTEND_ORIGIN` = `https://<your-vercel-app>.vercel.app`
  - `ENVIRONMENT=production`

Free tier spins the service down after inactivity — the first request
after idling takes ~10-30s to wake back up. Expected, not a bug.

## 3. Frontend — Vercel

- Root directory: `frontend`
- Framework preset: Vite (auto-detected)
- Environment variable: `VITE_API_BASE_URL` = `https://<your-render-app>.onrender.com`
  — **must be set before the build**, since Vite bakes `VITE_*` vars in
  at build time, not read at runtime like the backend's env vars.

## 4. Spotify Dashboard

Add a *second* Redirect URI (don't remove the `127.0.0.1` one — local
dev keeps using that):
```
https://<your-render-app>.onrender.com/auth/spotify/callback
```

Remember: this app is capped at 5 total test users in Spotify's
Development Mode (see README) — add real testers' emails under
Settings → User Management as needed.

## 5. Smoke test

```bash
curl https://<your-render-app>.onrender.com/health
```
Then open the Vercel URL in a browser and try the real login flow.
