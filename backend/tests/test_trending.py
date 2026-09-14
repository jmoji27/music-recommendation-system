"""'Hot right now' — most-reviewed albums, purely from our own
interactions table. No Spotify user-scoped call involved, so this is
unrestricted by Spotify's Development Mode user cap.
"""

import pytest
import respx
from httpx import Response

from tests.conftest import log_in_test_user

ALBUM_X = {
    "id": "album_x",
    "name": "Test Album X",
    "release_date": "2020-01-01",
    "images": [],
    "artists": [{"id": "artist_x", "name": "Artist X"}],
    "tracks": {"items": []},
}
ALBUM_Y = {
    "id": "album_y",
    "name": "Test Album Y",
    "release_date": "2021-01-01",
    "images": [],
    "artists": [{"id": "artist_y", "name": "Artist Y"}],
    "tracks": {"items": []},
}


def _mock_album_lookups(mock: respx.MockRouter) -> None:
    mock.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(200, json={"access_token": "app-token", "token_type": "Bearer", "expires_in": 3600})
    )
    mock.get("https://api.spotify.com/v1/albums/album_x").mock(return_value=Response(200, json=ALBUM_X))
    mock.get("https://api.spotify.com/v1/albums/album_y").mock(return_value=Response(200, json=ALBUM_Y))


@pytest.mark.asyncio
async def test_hot_albums_ranks_by_review_count_no_login_needed(client):
    # log_in_test_user opens its own respx.mock() internally, so it can't
    # be nested inside another one mocking the same token URL — do each
    # login as its own step, then mock album lookups separately.
    await log_in_test_user(client, spotify_id="hot_reviewer_1")
    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookups(mock)
        assert (await client.post("/albums/album_x/reviews", json={"stars": 5})).status_code == 201

    await log_in_test_user(client, spotify_id="hot_reviewer_2")
    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookups(mock)
        assert (await client.post("/albums/album_x/reviews", json={"stars": 4})).status_code == 201
        assert (await client.post("/albums/album_y/reviews", json={"stars": 3})).status_code == 201

    await client.post("/auth/spotify/logout")
    # limit=100: the dev database has real reviews from manual testing
    # sitting in it too (this hits the real, shared Postgres — not a
    # per-test-isolated one) — a small default limit could cut our two
    # test albums out entirely if enough real ones outrank them.
    response = await client.get("/hot-albums?limit=100")

    assert response.status_code == 200
    rows = response.json()
    spotify_ids = [row["spotify_id"] for row in rows]
    counts = {row["spotify_id"]: row["review_count"] for row in rows}

    assert counts["album_x"] == 2
    assert counts["album_y"] == 1
    # The core behavior under test: more-reviewed ranks ahead of less-reviewed.
    assert spotify_ids.index("album_x") < spotify_ids.index("album_y")
