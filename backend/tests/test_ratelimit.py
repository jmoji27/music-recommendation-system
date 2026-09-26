"""Rate limiting: safe-by-default baseline plus stricter per-route limits."""

import pytest
import respx
from httpx import Response

from app import ratelimit
from tests.conftest import log_in_test_user
from tests.helpers import mock_catalog


@pytest.mark.asyncio
async def test_baseline_write_limit_applies_to_any_unsafe_route(client):
    await log_in_test_user(client, spotify_id="rl_writer")
    limit = ratelimit.baseline_writes.limit

    statuses = [(await client.delete("/users/999999/follow")).status_code for _ in range(limit + 1)]
    assert statuses[:limit] == [204] * limit
    blocked = await client.delete("/users/999999/follow")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_limits_are_per_user_not_global(client):
    await log_in_test_user(client, spotify_id="rl_user_a")
    for _ in range(ratelimit.baseline_writes.limit):
        await client.delete("/users/999999/follow")
    assert (await client.delete("/users/999999/follow")).status_code == 429

    await log_in_test_user(client, spotify_id="rl_user_b")  # a different person
    assert (await client.delete("/users/999999/follow")).status_code == 204


@pytest.mark.asyncio
async def test_anonymous_requests_are_limited_by_ip(client):
    limit = ratelimit.baseline_reads.limit
    for _ in range(limit):
        await client.get("/health")
    assert (await client.get("/health")).status_code == 429


@pytest.mark.asyncio
async def test_expensive_catalog_route_has_a_stricter_limit(client):
    limit = ratelimit.catalog_limit.limit
    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        codes = [(await client.get("/catalog/tracks/search", params={"q": "x"})).status_code for _ in range(limit + 1)]
    assert codes[:limit] == [200] * limit
    assert codes[limit] == 429
    assert limit < ratelimit.baseline_reads.limit  # stricter than the baseline, by design


@pytest.mark.asyncio
async def test_gemini_backed_routes_share_one_tight_budget(client):
    await log_in_test_user(client, spotify_id="rl_gemini")
    limit = ratelimit.gemini_limit.limit
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600})
        )
        mock.get("https://api.spotify.com/v1/me/top/artists").mock(return_value=Response(200, json={"items": []}))
        mock.get("https://api.spotify.com/v1/me/player/recently-played").mock(
            return_value=Response(200, json={"items": []})
        )
        for i in range(limit):
            path = "/me/taste-summary" if i % 2 else "/me/recommendations"
            assert (await client.get(path)).status_code == 200
        assert (await client.get("/me/taste-summary")).status_code == 429
        assert (await client.get("/me/recommendations")).status_code == 429


@pytest.mark.asyncio
async def test_window_expires_and_requests_are_allowed_again(client, monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock["now"])

    for _ in range(ratelimit.baseline_reads.limit):
        await client.get("/health")
    assert (await client.get("/health")).status_code == 429

    clock["now"] += ratelimit.baseline_reads.window + 1
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_can_be_disabled_by_config(client, monkeypatch):
    monkeypatch.setattr("app.ratelimit.settings.rate_limit_enabled", False)
    for _ in range(ratelimit.baseline_reads.limit + 5):
        assert (await client.get("/health")).status_code == 200
