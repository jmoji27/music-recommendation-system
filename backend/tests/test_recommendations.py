"""One-shot LLM taste recommendations. Gemini itself is mocked (not
respx-based — the SDK doesn't necessarily route through httpx the same
way) by patching the async client call directly. The "not configured"
path is tested for real, since GEMINI_API_KEY is empty by default in
this test environment.
"""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from app.services.recommendations import TasteRecommendation, generate_taste_recommendation
from tests.conftest import log_in_test_user


@pytest.mark.asyncio
async def test_recommendations_not_available_without_api_key(client, monkeypatch):
    # Explicit, not ambient: this must hold regardless of whether the
    # developer's real .env happens to have a real key in it (it does,
    # now — this test broke for exactly that reason before this pin).
    monkeypatch.setattr("app.services.recommendations.settings.gemini_api_key", "")
    await log_in_test_user(client, spotify_id="rec_user_1")

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600})
        )
        mock.get("https://api.spotify.com/v1/me/top/artists").mock(
            return_value=Response(200, json={"items": []})
        )
        mock.get("https://api.spotify.com/v1/me/player/recently-played").mock(
            return_value=Response(200, json={"items": []})
        )
        response = await client.get("/me/recommendations")

    assert response.status_code == 200
    assert response.json() == {"available": False, "reason": "not_configured"}


@pytest.mark.asyncio
async def test_generate_taste_recommendation_parses_gemini_response(monkeypatch):
    monkeypatch.setattr("app.services.recommendations.settings.gemini_api_key", "fake-key-for-test")

    fake_interaction = type(
        "FakeInteraction",
        (),
        {
            "output_text": TasteRecommendation(
                summary="You love moody, atmospheric guitar music.",
                recommended_genres=["slowcore", "post-rock"],
                recommended_artists=["Duster", "Codeine"],
            ).model_dump_json()
        },
    )()

    with patch("app.services.recommendations.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.aio.interactions.create = AsyncMock(return_value=fake_interaction)

        result = await generate_taste_recommendation({"shoegaze": 3}, ["Slowdive"])

    assert result["available"] is True
    assert result["summary"] == "You love moody, atmospheric guitar music."
    assert result["recommended_genres"] == ["slowcore", "post-rock"]
    assert result["recommended_artists"] == ["Duster", "Codeine"]


@pytest.mark.asyncio
async def test_generate_taste_recommendation_degrades_gracefully_on_gemini_failure(monkeypatch):
    """Verified live: hitting Gemini's free-tier rate limit (20
    requests/day) previously crashed this with a raw 500 instead of
    the graceful {"available": False} every other failure mode gets.
    """
    monkeypatch.setattr("app.services.recommendations.settings.gemini_api_key", "fake-key-for-test")

    with patch("app.services.recommendations.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.aio.interactions.create = AsyncMock(side_effect=RuntimeError("429 rate limited"))
        result = await generate_taste_recommendation({"shoegaze": 3}, ["Slowdive"])

    assert result == {"available": False, "reason": "error"}
