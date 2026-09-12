"""Thin wrapper around the Spotify Web API endpoints this app uses.

No caching, retries, or upsert logic here — this module only talks to
Spotify and returns raw JSON. Turning that JSON into local rows lives in
spotify_sync.py, so this stays easy to unit-test with a mocked HTTP layer.
"""

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
