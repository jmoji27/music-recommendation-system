"""Genre breakdown + recent-listening estimate. The "recent" framing
matters: Spotify's API has no annual listening-time endpoint (that's
Wrapped-exclusive), so this is deliberately built from recently-played
tracks, not a real year-to-date total — see app/services/taste.py.
"""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from app.models.spotify_entities import Artist
from tests.conftest import log_in_test_user


def _mock_taste_data(mock: respx.MockRouter) -> None:
    mock.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(200, json={"access_token": "user-token", "token_type": "Bearer", "expires_in": 3600})
    )
    mock.get("https://api.spotify.com/v1/me/top/artists").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {"id": "a1", "name": "Artist One", "genres": ["dream pop", "shoegaze"], "images": []},
                    {"id": "a2", "name": "Artist Two", "genres": ["shoegaze"], "images": []},
                    {"id": "a3", "name": "Artist Three", "genres": ["dream pop"], "images": []},
                ]
            },
        )
    )
    mock.get("https://api.spotify.com/v1/me/player/recently-played").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {"track": {"duration_ms": 180000}},  # 3 min
                    {"track": {"duration_ms": 240000}},  # 4 min
                ]
            },
        )
    )


@pytest.mark.asyncio
async def test_taste_summary_aggregates_genres_and_recent_minutes(client):
    await log_in_test_user(client, spotify_id="taste_user_1")

    with respx.mock(assert_all_called=False) as mock:
        _mock_taste_data(mock)
        response = await client.get("/me/taste-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["genre_counts"] == {"dream pop": 2, "shoegaze": 2}
    assert body["top_genre"] in ("dream pop", "shoegaze")
    assert body["recent_minutes_listened"] == 7  # 3 + 4 minutes
    assert body["recent_track_count"] == 2
    assert set(body["top_artist_names"]) == {"Artist One", "Artist Two", "Artist Three"}


@pytest.mark.asyncio
async def test_taste_summary_requires_auth(client):
    response = await client.get("/me/taste-summary")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_taste_summary_classifies_via_gemini_when_spotify_genres_empty(client, db_session):
    """The realistic case: Spotify returns no genres at all (verified live
    against their real API), so classification falls to Gemini, and the
    result is persisted onto the Artist row for future requests to reuse.
    """
    await log_in_test_user(client, spotify_id="taste_user_2")

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600})
        )
        mock.get("https://api.spotify.com/v1/me/top/artists").mock(
            return_value=Response(
                200,
                json={"items": [{"id": "b1", "name": "Real Artist", "genres": [], "images": []}]},
            )
        )
        mock.get("https://api.spotify.com/v1/me/player/recently-played").mock(
            return_value=Response(200, json={"items": []})
        )

        with patch("app.services.genre_classification.settings.gemini_api_key", "fake-key"):
            fake_interaction = type(
                "FakeInteraction", (), {"output_text": '{"genres": {"Real Artist": "hyperpop"}}'}
            )()
            with patch("app.services.genre_classification.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.aio.interactions.create = AsyncMock(return_value=fake_interaction)
                response = await client.get("/me/taste-summary")

    assert response.status_code == 200
    assert response.json()["genre_counts"] == {"hyperpop": 1}

    artist = await db_session.scalar(select(Artist).where(Artist.spotify_id == "b1"))
    assert artist.genres == ["hyperpop"]  # persisted, not just returned in this response


@pytest.mark.asyncio
async def test_taste_summary_survives_gemini_failure(client):
    """Verified live: hitting Gemini's free-tier rate limit (20
    requests/day for gemini-3.8-flash) crashed this whole endpoint with
    a raw 500 before genre_classification.py caught it — /me/taste-summary
    loads automatically on every visit to the Taste page, so a Gemini
    outage must degrade to empty genre data, not take the page down.
    """
    await log_in_test_user(client, spotify_id="taste_user_3")

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600})
        )
        mock.get("https://api.spotify.com/v1/me/top/artists").mock(
            return_value=Response(
                200,
                json={"items": [{"id": "b2", "name": "Another Artist", "genres": [], "images": []}]},
            )
        )
        mock.get("https://api.spotify.com/v1/me/player/recently-played").mock(
            return_value=Response(200, json={"items": []})
        )

        with patch("app.services.genre_classification.settings.gemini_api_key", "fake-key"):
            with patch("app.services.genre_classification.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.aio.interactions.create = AsyncMock(
                    side_effect=RuntimeError("429 rate limited")
                )
                response = await client.get("/me/taste-summary")

    assert response.status_code == 200
    assert response.json()["genre_counts"] == {}
