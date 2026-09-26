"""Session lifetime/renewal, forged tokens, and the production secret guard."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from pydantic import ValidationError

from app.config import Settings, settings
from app.security import decode_session_token
from tests.conftest import log_in_test_user


def _token(user_id: int, *, expires_in: timedelta, auth_ago: timedelta = timedelta(0), secret: str | None = None,
           include_auth_at: bool = True) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "exp": now + expires_in}
    if include_auth_at:
        payload["auth_at"] = int((now - auth_ago).timestamp())
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def _my_id(client) -> int:
    return (await client.get("/me")).json()["id"]


@pytest.mark.asyncio
async def test_session_renews_when_less_than_half_the_lifetime_is_left(client):
    await log_in_test_user(client, spotify_id="renew_user")
    uid = await _my_id(client)

    client.cookies.set("session", _token(uid, expires_in=timedelta(minutes=10)))
    response = await client.get("/me")
    assert response.status_code == 200
    assert "session=" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_fresh_session_is_not_reissued_on_every_request(client):
    await log_in_test_user(client, spotify_id="no_renew_user")
    uid = await _my_id(client)

    client.cookies.set("session", _token(uid, expires_in=timedelta(minutes=55)))
    response = await client.get("/me")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_renewal_keeps_the_original_login_time(client):
    """Otherwise an active session could renew itself forever."""
    await log_in_test_user(client, spotify_id="auth_at_user")
    uid = await _my_id(client)
    logged_in_ten_days_ago = timedelta(days=10)

    client.cookies.set("session", _token(uid, expires_in=timedelta(minutes=5), auth_ago=logged_in_ten_days_ago))
    response = await client.get("/me")
    renewed = response.headers["set-cookie"].split("session=")[1].split(";")[0]

    claims = decode_session_token(renewed)
    age = datetime.now(timezone.utc) - claims["auth_at_dt"]
    assert timedelta(days=9, hours=23) < age < timedelta(days=10, hours=1)


@pytest.mark.asyncio
async def test_session_older_than_the_absolute_cap_is_rejected_even_if_unexpired(client):
    await log_in_test_user(client, spotify_id="capped_user")
    uid = await _my_id(client)

    stale = _token(uid, expires_in=timedelta(minutes=50), auth_ago=timedelta(days=settings.session_max_age_days + 1))
    client.cookies.set("session", stale)
    assert (await client.get("/me")).status_code == 401


@pytest.mark.asyncio
async def test_tokens_missing_auth_at_or_signed_with_another_secret_are_rejected(client):
    await log_in_test_user(client, spotify_id="forge_user")
    uid = await _my_id(client)

    client.cookies.set("session", _token(uid, expires_in=timedelta(minutes=30), include_auth_at=False))
    assert (await client.get("/me")).status_code == 401

    forged = _token(uid, expires_in=timedelta(minutes=30), secret="not-the-real-secret-not-the-real-secret")
    client.cookies.set("session", forged)
    assert (await client.get("/me")).status_code == 401


def test_production_refuses_placeholder_or_short_jwt_secrets():
    for bad in ("change-me-in-.env", "change-me-generate-a-random-value", "", "too-short"):
        with pytest.raises(ValidationError):
            Settings(environment="production", jwt_secret=bad, _env_file=None)
    assert Settings(environment="production", jwt_secret="x" * 40, _env_file=None).is_production


def test_development_only_warns_about_a_weak_secret(caplog):
    with caplog.at_level("WARNING"):
        Settings(environment="development", jwt_secret="change-me-in-.env", _env_file=None)
    assert "JWT_SECRET" in caplog.text
