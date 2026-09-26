"""Exercises the full Spotify OAuth login -> callback -> now-playing flow
with Spotify's own API mocked (respx), against the real Postgres schema
(via the db_session/client fixtures in conftest.py), so this checks both
our code AND that it actually fits the schema/constraints we built.
"""

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from app.config import settings
from app.models.spotify_entities import Album, Artist, Track
from app.models.user import User
from tests.conftest import log_in_test_user


@pytest.mark.asyncio
async def test_login_sets_signed_state_cookie(client):
    response = await client.get("/auth/spotify/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.spotify.com/authorize" in response.headers["location"]
    assert "oauth_state" in response.cookies


@pytest.mark.asyncio
async def test_callback_rejects_mismatched_state(client):
    response = await client.get(
        "/auth/spotify/callback",
        params={"code": "irrelevant", "state": "not-a-real-token"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "login_error=expired" in response.headers["location"]


@pytest.mark.asyncio
async def test_full_login_and_now_playing_flow(client, db_session):
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fake-access-token",
                    "refresh_token": "fake-refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )
        mock.get("https://api.spotify.com/v1/me").mock(
            return_value=Response(
                200,
                json={
                    "id": "spotify_test_user_1",
                    "display_name": "Test User",
                    "email": "test@example.com",
                    "images": [],
                },
            )
        )
        mock.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
            return_value=Response(
                200,
                json={
                    "is_playing": True,
                    "progress_ms": 12345,
                    "item": {
                        "id": "spotify_track_1",
                        "name": "Test Track",
                        "duration_ms": 200000,
                        "artists": [{"id": "spotify_artist_1", "name": "Test Artist"}],
                        "album": {
                            "id": "spotify_album_1",
                            "name": "Test Album",
                            "release_date": "2020-01-01",
                            "images": [{"url": "http://example.com/cover.jpg"}],
                        },
                    },
                },
            )
        )

        login_response = await client.get("/auth/spotify/login", follow_redirects=False)
        state = login_response.cookies["oauth_state"]

        callback_response = await client.get(
            "/auth/spotify/callback", params={"code": "fake-code", "state": state}, follow_redirects=False
        )
        assert callback_response.status_code == 302
        assert callback_response.headers["location"] == settings.frontend_origin
        assert "session" in callback_response.cookies

        now_playing_response = await client.get("/me/now-playing")
        assert now_playing_response.status_code == 200
        body = now_playing_response.json()

    assert body["is_playing"] is True
    assert body["track"]["name"] == "Test Track"
    assert body["album"]["name"] == "Test Album"
    assert body["artist"]["name"] == "Test Artist"

    # Confirm the rows actually landed correctly-linked in Postgres, not
    # just that the JSON response looked right.
    user = await db_session.scalar(select(User).where(User.spotify_id == "spotify_test_user_1"))
    assert user is not None
    assert user.email == "test@example.com"
    assert user.spotify_access_token_encrypted != "fake-access-token"  # must be encrypted, not plaintext

    artist = await db_session.scalar(select(Artist).where(Artist.spotify_id == "spotify_artist_1"))
    album = await db_session.scalar(select(Album).where(Album.spotify_id == "spotify_album_1"))
    track = await db_session.scalar(select(Track).where(Track.spotify_id == "spotify_track_1"))
    assert artist is not None and album is not None and track is not None
    assert album.artist_id == artist.id
    assert track.album_id == album.id
    assert track.artist_id == artist.id


@pytest.mark.asyncio
async def test_now_playing_requires_auth(client):
    response = await client.get("/me/now-playing")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_session_cookie(client):
    await log_in_test_user(client, spotify_id="logout_test_user")
    assert client.cookies.get("session") is not None

    logout_response = await client.post("/auth/spotify/logout")
    assert logout_response.status_code == 204
    # httpx's cookie jar honors the clearing Set-Cookie the same way a
    # real browser would, so this proves the cookie is actually gone,
    # not just that the endpoint returned success.
    assert client.cookies.get("session") is None

    response = await client.get("/me/now-playing")
    assert response.status_code == 401
