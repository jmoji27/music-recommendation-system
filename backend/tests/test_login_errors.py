"""Login failures send people back to the app with a reason instead of a raw error page."""

import pytest
import respx
from httpx import ConnectError, Response

from app.config import settings

PROVIDERS = {
    "spotify": ("https://accounts.spotify.com/api/token", "spotify_client_id"),
    "google": ("https://oauth2.googleapis.com/token", "google_client_id"),
}


@pytest.mark.asyncio
async def test_providers_reflect_configuration(client, monkeypatch):
    body = (await client.get("/auth/providers")).json()
    assert body == {"spotify": True, "google": True}

    monkeypatch.setattr(settings, "google_client_secret", "")
    body = (await client.get("/auth/providers")).json()
    assert body == {"spotify": True, "google": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_unconfigured_login_redirects_with_reason(client, monkeypatch, provider):
    monkeypatch.setattr(settings, f"{provider}_client_secret", "")
    response = await client.get(f"/auth/{provider}/login", follow_redirects=False)
    assert response.status_code == 302
    assert f"login_error=not_configured&provider={provider}" in response.headers["location"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_bad_state_redirects_expired(client, provider):
    response = await client.get(
        f"/auth/{provider}/callback", params={"code": "x", "state": "nope"}, follow_redirects=False
    )
    assert response.status_code == 302
    assert "login_error=expired" in response.headers["location"]
    assert "session" not in response.cookies


async def _callback(client, provider):
    login = await client.get(f"/auth/{provider}/login", follow_redirects=False)
    state = login.cookies["oauth_state"]
    return await client.get(
        f"/auth/{provider}/callback", params={"code": "c", "state": state}, follow_redirects=False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_token_exchange_rejected_redirects_failed(client, provider):
    token_url, _ = PROVIDERS[provider]
    with respx.mock(assert_all_called=False) as mock:
        mock.post(token_url).mock(return_value=Response(400, json={"error": "invalid_grant"}))
        response = await _callback(client, provider)
    assert response.status_code == 302
    assert "login_error=failed" in response.headers["location"]
    assert "session" not in response.cookies


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_network_error_redirects_failed(client, provider):
    token_url, _ = PROVIDERS[provider]
    with respx.mock(assert_all_called=False) as mock:
        mock.post(token_url).mock(side_effect=ConnectError("boom"))
        response = await _callback(client, provider)
    assert "login_error=failed" in response.headers["location"]


@pytest.mark.asyncio
async def test_spotify_403_on_profile_means_not_allowlisted(client):
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(
                200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "token_type": "Bearer"}
            )
        )
        mock.get("https://api.spotify.com/v1/me").mock(return_value=Response(403, json={"error": "forbidden"}))
        response = await _callback(client, "spotify")
    assert "login_error=not_allowlisted" in response.headers["location"]
    assert "session" not in response.cookies
