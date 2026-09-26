"""Thin wrapper around the Spotify Web API endpoints this app uses.

No caching, retries, or upsert logic here — this module only talks to
Spotify and returns raw JSON. Turning that JSON into local rows lives in
spotify_sync.py, so this stays easy to unit-test with a mocked HTTP layer.
"""

import time
import urllib.parse

import httpx

from app.config import settings

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# user-read-email: to populate User.email at signup.
# user-read-currently-playing / user-read-playback-state: the "now playing" feature.
# user-top-read / user-read-recently-played: for the taste/recommendation module later.
SCOPES = [
    "user-read-email",
    "user-read-currently-playing",
    "user-read-playback-state",
    "user-top-read",
    "user-read-recently-played",
]


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        # Without this, Spotify silently re-approves and redirects back
        # if the browser already has an active Spotify session that
        # previously granted this app access — meaning "log out, then
        # connect again" would just log back into the same account with
        # no prompt. show_dialog forces the consent screen to reappear
        # (with a "not you?" option), so a second person on the same
        # browser actually gets a chance to switch accounts.
        "show_dialog": "true",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
            },
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
        response.raise_for_status()
        return response.json()


async def get_current_user_profile(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()


async def get_top_tracks(access_token: str, time_range: str = "medium_term", limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me/top/tracks",
            params={"time_range": time_range, "limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()["items"]


async def get_top_artists(access_token: str, time_range: str = "medium_term", limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me/top/artists",
            params={"time_range": time_range, "limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()["items"]


async def get_recently_played(access_token: str, limit: int = 50) -> list[dict]:
    """Up to the last 50 played tracks with timestamps. This is the closest
    thing to a "listening history" Spotify's public API exposes — there is
    no endpoint for total/annual listening time (that's Wrapped-exclusive,
    computed from Spotify's internal data, never exposed to third-party
    apps). Any "time listened" stat built from this is an estimate over a
    short recent window, not a real year-to-date total.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me/player/recently-played",
            params={"limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()["items"]


async def get_currently_playing(access_token: str) -> dict | None:
    """None means "nothing is playing" (Spotify returns 204 for that)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me/player/currently-playing",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code == 204:
        return None
    response.raise_for_status()
    return response.json()


# ── App-level (Client Credentials) access, for public catalog lookups ──
#
# Search and "get album/artist by id" are public catalog data, not tied to
# any specific user, so they use Spotify's Client Credentials flow (the
# backend authenticating as itself) instead of a logged-in user's token.
# One token is shared process-wide and refreshed when it's close to
# expiring — simple in-memory cache, fine for a single-process deploy.

_app_token: str | None = None
_app_token_expires_at: float = 0.0


async def _get_app_access_token() -> str:
    global _app_token, _app_token_expires_at

    if _app_token and time.monotonic() < _app_token_expires_at - 30:
        return _app_token

    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
        response.raise_for_status()
        token_data = response.json()

    _app_token = token_data["access_token"]
    _app_token_expires_at = time.monotonic() + token_data["expires_in"]
    return _app_token


async def search_albums(query: str, limit: int = 10) -> list[dict]:
    token = await _get_app_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "album", "limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()["albums"]["items"]


async def search_tracks(query: str, limit: int = 10) -> list[dict]:
    token = await _get_app_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "track", "limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()["tracks"]["items"]


async def get_track(spotify_track_id: str) -> dict:
    token = await _get_app_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/tracks/{spotify_track_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()


async def get_album(spotify_album_id: str) -> dict:
    token = await _get_app_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/albums/{spotify_album_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()
