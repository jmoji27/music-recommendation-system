"""Reviews/comments/likes on the interactions table. Album caching is
mocked (respx) since it's not the point of these tests; the point is
verifying the create/list/comment/like logic and its constraints
against the real schema.
"""

import pytest
import respx
from httpx import Response

from tests.conftest import log_in_test_user

ALBUM_DETAIL_RESPONSE = {
    "id": "album_x",
    "name": "Test Album X",
    "release_date": "2020-01-01",
    "images": [{"url": "http://example.com/x.jpg"}],
    "artists": [{"id": "artist_x", "name": "Artist X"}],
    "tracks": {"items": []},
}


def _mock_album_lookup(mock: respx.MockRouter) -> None:
    mock.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "app-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )
    mock.get("https://api.spotify.com/v1/albums/album_x").mock(return_value=Response(200, json=ALBUM_DETAIL_RESPONSE))


@pytest.mark.asyncio
async def test_create_review_lazily_caches_album(client):
    await log_in_test_user(client, spotify_id="reviewer_1")

    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        response = await client.post("/albums/album_x/reviews", json={"stars": 5, "content": "Loved it."})

    assert response.status_code == 201
    body = response.json()
    assert body["stars"] == 5
    assert body["content"] == "Loved it."
    assert body["like_count"] == 0
    assert body["comments"] == []
    assert body["user"]["display_name"] == "Test User"


@pytest.mark.asyncio
async def test_review_requires_stars_or_content(client):
    await log_in_test_user(client, spotify_id="reviewer_2")
    response = await client.post("/albums/album_x/reviews", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_review_conflicts(client):
    await log_in_test_user(client, spotify_id="reviewer_3")

    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        first = await client.post("/albums/album_x/reviews", json={"stars": 4})
        second = await client.post("/albums/album_x/reviews", json={"stars": 2})

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_comment_and_like_flow(client):
    await log_in_test_user(client, spotify_id="author_1")
    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        review_response = await client.post("/albums/album_x/reviews", json={"stars": 5})
    review_id = review_response.json()["id"]

    # A second user comments on and likes the first user's review.
    await log_in_test_user(client, spotify_id="commenter_1")
    comment_response = await client.post(f"/reviews/{review_id}/comments", json={"content": "Totally agree!"})
    assert comment_response.status_code == 201
    comment_id = comment_response.json()["id"]

    like_review_response = await client.post(f"/reviews/{review_id}/like")
    assert like_review_response.status_code == 201

    like_comment_response = await client.post(f"/comments/{comment_id}/like")
    assert like_comment_response.status_code == 201

    # Liking the same review again should conflict, not double-count.
    duplicate_like = await client.post(f"/reviews/{review_id}/like")
    assert duplicate_like.status_code == 409

    listing = await client.get("/albums/album_x/reviews")
    assert listing.status_code == 200
    reviews = listing.json()
    assert len(reviews) == 1
    assert reviews[0]["like_count"] == 1
    assert len(reviews[0]["comments"]) == 1
    assert reviews[0]["comments"][0]["content"] == "Totally agree!"
    assert reviews[0]["comments"][0]["like_count"] == 1


@pytest.mark.asyncio
async def test_comment_on_nonexistent_review_404s(client):
    await log_in_test_user(client, spotify_id="commenter_2")
    response = await client.post("/reviews/999999/comments", json={"content": "hi"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_review_requires_auth(client):
    response = await client.post("/albums/album_x/reviews", json={"stars": 3})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_reviews_for_unknown_album_returns_empty(client):
    response = await client.get("/albums/some_never_seen_album/reviews")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_top_album_conversations_only_includes_albums_with_reviews(client):
    await log_in_test_user(client, spotify_id="conversations_user")

    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        review_response = await client.post("/albums/album_x/reviews", json={"stars": 4, "content": "Solid."})
    assert review_response.status_code == 201

    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(200, json={"access_token": "user-token", "token_type": "Bearer", "expires_in": 3600})
        )
        mock.get("https://api.spotify.com/v1/me/top/tracks").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "track_reviewed_album",
                            "name": "Track On Reviewed Album",
                            "duration_ms": 200000,
                            "artists": [{"id": "artist_x", "name": "Artist X"}],
                            "album": ALBUM_DETAIL_RESPONSE,
                        },
                        {
                            "id": "track_unreviewed_album",
                            "name": "Track On Unreviewed Album",
                            "duration_ms": 180000,
                            "artists": [{"id": "artist_y", "name": "Artist Y"}],
                            "album": {
                                "id": "album_y",
                                "name": "Untouched Album",
                                "release_date": "2019-01-01",
                                "images": [],
                            },
                        },
                    ]
                },
            )
        )

        response = await client.get("/me/top-albums/conversations")

    assert response.status_code == 200
    conversations = response.json()
    assert len(conversations) == 1
    assert conversations[0]["spotify_album_id"] == "album_x"
    assert conversations[0]["album"]["name"] == "Test Album X"
    assert len(conversations[0]["reviews"]) == 1
    assert conversations[0]["reviews"][0]["content"] == "Solid."
