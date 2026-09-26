# Running this project locally

Quick reference for starting everything up. See `README.md` for
architecture/design context — this file is just "how do I run it."

## Prerequisites (one-time)

- Postgres running locally with the `music_rec` database created (see
  README's "Local dev setup" for the one-time `sudo -u postgres psql`
  setup if you haven't done this yet).
- `backend/.env` filled in (copy from `backend/.env.example`) — needs
  `DATABASE_URL`, `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` (from the
  [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)),
  `TOKEN_ENCRYPTION_KEY`, and `JWT_SECRET` (random, 32+ characters:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
  Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
  from Google Cloud Console to enable "Continue with Google" (the button
  is hidden until they're set).
- Backend Python deps installed: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Frontend deps installed: `cd frontend && npm install`
- Migrations applied: `cd backend && source .venv/bin/activate && alembic upgrade head`

## Every time you want to run it

Open two terminal tabs and leave both running.

**Terminal 1 — backend** (from `backend/`):
```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — frontend** (from `frontend/`):
```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open **`http://127.0.0.1:5173`** in your browser.

> **Always use `127.0.0.1`, never `localhost`**, for both the backend
> and frontend URLs. The backend's CORS config and Spotify's OAuth
> redirect URI are both pinned to `127.0.0.1` — mixing in `localhost`
> anywhere breaks cross-origin requests and/or the login flow's CSRF
> cookie check.

## Checking things

```bash
curl http://127.0.0.1:8000/health   # backend alive?
curl http://127.0.0.1:5173          # frontend alive?
```

Interactive API docs (try any endpoint, including POSTs, right from
the browser): `http://127.0.0.1:8000/docs`

## Stopping / restarting

```bash
lsof -ti:8000 -sTCP:LISTEN   # backend's PID
lsof -ti:5173 -sTCP:LISTEN   # frontend's PID
kill <pid>
```

Or just `Ctrl+C` in whichever terminal tab is running it.

## Spotify login

Visit `http://127.0.0.1:8000/auth/spotify/login` (or click "Connect
with Spotify" in the frontend) to go through the real OAuth flow.
Sessions renew while you're active and expire 30 days after you log in
(`SESSION_MAX_AGE_DAYS`). Changing `JWT_SECRET` logs everyone out. After
pulling new code, run `alembic upgrade head` again and restart uvicorn —
the `--reload` flag isn't always on, so a stale server keeps the old code.
