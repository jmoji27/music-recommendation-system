"""Google OAuth for login only — unlike Spotify, we never call Google's
API again after the initial login (no ongoing token storage needed).
Scope is intentionally minimal: just enough to identify the person and
show their name/picture, nothing else.
"""

import urllib.parse

import httpx

from app.config import settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = ["openid", "email", "profile"]


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "response_type": "code",
        "redirect_uri": settings.google_redirect_uri,
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
                "redirect_uri": settings.google_redirect_uri,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_user_info(access_token: str) -> dict:
    """Returns Google's profile fields: sub (their user id), email,
    name, picture."""
    async with httpx.AsyncClient() as client:
        response = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        return response.json()
