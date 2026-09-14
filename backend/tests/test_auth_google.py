"""Google login: a second, independent way to get an account, with no
Spotify data attached unless/until that account also connects Spotify.
"""

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from tests.conftest import log_in_test_user


def _mock_google(mock: respx.MockRouter, sub: str, email: str, name: str = "Test Googler") -> None:
    mock.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(200, json={"access_token": "google-access-token", "token_type": "Bearer", "expires_in": 3600})
    )
    mock.get("https://www.googleapis.com/oauth2/v3/userinfo").mock(
        return_value=Response(200, json={"sub": sub, "email": email, "name": name, "picture": "http://example.com/pic.jpg"})
    )


async def _log_in_with_google(client, sub: str, email: str, name: str = "Test Googler") -> None:
    with respx.mock(assert_all_called=False) as mock:
        _mock_google(mock, sub, email, name)
        login_response = await client.get("/auth/google/login", follow_redirects=False)
        state = login_response.cookies["oauth_state"]
        callback_response = await client.get(
            "/auth/google/callback", params={"code": "fake-code", "state": state}, follow_redirects=False
        )
        assert callback_response.status_code == 302
        assert callback_response.headers["location"] == settings.frontend_origin
        assert "session" in callback_response.cookies


@pytest.mark.asyncio
async def test_google_login_redirects_to_google(client):
    response = await client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    assert "oauth_state" in response.cookies


@pytest.mark.asyncio
async def test_google_callback_creates_user_without_spotify(client, db_session):
    await _log_in_with_google(client, sub="google_sub_1", email="googler1@example.com")

    user = await db_session.scalar(select(User).where(User.google_id == "google_sub_1"))
    assert user is not None
    assert user.spotify_id is None
    assert user.has_spotify is False

    me = await client.get("/me")
    assert me.status_code == 200
    assert me.json()["has_spotify"] is False


@pytest.mark.asyncio
async def test_google_only_user_gets_403_on_spotify_features(client):
    await _log_in_with_google(client, sub="google_sub_2", email="googler2@example.com")

    response = await client.get("/me/top-tracks")
    assert response.status_code == 403
    assert "Google" in response.json()["detail"]


@pytest.mark.asyncio
async def test_google_login_links_onto_existing_account_with_same_email(client, db_session):
    # Same email used for both providers — should link onto one account,
    # not create a second, disconnected one.
    await log_in_test_user(client, spotify_id="linking_spotify_user")
    spotify_user = await db_session.scalar(select(User).where(User.spotify_id == "linking_spotify_user"))
    shared_email = spotify_user.email
    original_id = spotify_user.id

    await client.post("/auth/spotify/logout")
    await _log_in_with_google(client, sub="google_sub_linked", email=shared_email)

    linked_user = await db_session.scalar(select(User).where(User.google_id == "google_sub_linked"))
    assert linked_user.id == original_id
    assert linked_user.spotify_id == "linking_spotify_user"
    assert linked_user.has_spotify is True
