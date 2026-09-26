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


async def _review_as(client, spotify_id: str, **payload) -> int:
    await log_in_test_user(client, spotify_id=spotify_id)
    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        response = await client.post("/albums/album_x/reviews", json=payload)
    return response.json()["id"]


@pytest.mark.asyncio
async def test_edit_review_updates_and_marks_edited(client):
    review_id = await _review_as(client, "editor_1", stars=3, content="Meh.")

    response = await client.put(f"/reviews/{review_id}", json={"stars": 5, "content": "Grew on me."})
    assert response.status_code == 200
    body = response.json()
    assert (body["stars"], body["content"], body["edited"]) == (5, "Grew on me.", True)

    listed = (await client.get("/albums/album_x/reviews")).json()[0]
    assert listed["stars"] == 5 and listed["edited"] is True


@pytest.mark.asyncio
async def test_unedited_review_is_not_marked_edited(client):
    await _review_as(client, "editor_2", stars=3)
    assert (await client.get("/albums/album_x/reviews")).json()[0]["edited"] is False


@pytest.mark.asyncio
async def test_edit_review_can_drop_stars_but_not_everything(client):
    review_id = await _review_as(client, "editor_3", stars=4, content="Nice.")
    ok = await client.put(f"/reviews/{review_id}", json={"content": "Nice."})
    assert ok.status_code == 200 and ok.json()["stars"] is None
    empty = await client.put(f"/reviews/{review_id}", json={})
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_cannot_edit_or_delete_someone_elses_review(client):
    review_id = await _review_as(client, "owner_1", stars=5, content="Mine.")
    await log_in_test_user(client, spotify_id="intruder_1")

    assert (await client.put(f"/reviews/{review_id}", json={"stars": 1})).status_code == 403
    assert (await client.delete(f"/reviews/{review_id}")).status_code == 403

    await log_in_test_user(client, spotify_id="owner_1")
    listed = (await client.get("/albums/album_x/reviews")).json()[0]
    assert listed["stars"] == 5 and listed["content"] == "Mine."


@pytest.mark.asyncio
async def test_edit_delete_require_login_and_404_for_missing(client):
    assert (await client.put("/reviews/1", json={"stars": 1})).status_code == 401
    assert (await client.delete("/reviews/1")).status_code == 401
    await log_in_test_user(client, spotify_id="nobody_1")
    assert (await client.put("/reviews/999999", json={"stars": 1})).status_code == 404
    assert (await client.delete("/reviews/999999")).status_code == 404
    assert (await client.delete("/comments/999999")).status_code == 404


@pytest.mark.asyncio
async def test_delete_review_removes_its_comments_and_likes(client, db_session):
    from sqlalchemy import func, or_, select

    from app.models.interaction import Interaction

    review_id = await _review_as(client, "del_owner", stars=2)
    await log_in_test_user(client, spotify_id="del_fan")
    await client.post(f"/reviews/{review_id}/comments", json={"content": "hi"})
    await client.post(f"/reviews/{review_id}/like")

    await log_in_test_user(client, spotify_id="del_owner")
    assert (await client.delete(f"/reviews/{review_id}")).status_code == 204

    assert (await client.get("/albums/album_x/reviews")).json() == []
    leftovers = await db_session.scalar(
        select(func.count())
        .select_from(Interaction)
        .where(or_(Interaction.id == review_id, Interaction.parent_interaction_id == review_id))
    )
    assert leftovers == 0


@pytest.mark.asyncio
async def test_deleting_review_lets_you_review_again(client):
    review_id = await _review_as(client, "again_1", stars=1)
    await client.delete(f"/reviews/{review_id}")
    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        again = await client.post("/albums/album_x/reviews", json={"stars": 5})
    assert again.status_code == 201


@pytest.mark.asyncio
async def test_comment_edit_and_delete_permissions(client):
    review_id = await _review_as(client, "thread_owner", stars=4)
    await log_in_test_user(client, spotify_id="thread_author")
    comment_id = (await client.post(f"/reviews/{review_id}/comments", json={"content": "first"})).json()["id"]

    edited = await client.put(f"/comments/{comment_id}", json={"content": "second"})
    assert edited.status_code == 200
    assert edited.json()["content"] == "second" and edited.json()["edited"] is True
    assert (await client.put(f"/comments/{comment_id}", json={"content": ""})).status_code == 422

    # A bystander can neither edit nor delete it.
    await log_in_test_user(client, spotify_id="thread_bystander")
    assert (await client.put(f"/comments/{comment_id}", json={"content": "x"})).status_code == 403
    assert (await client.delete(f"/comments/{comment_id}")).status_code == 403

    # The review's author can't rewrite it, but can remove it from their thread.
    await log_in_test_user(client, spotify_id="thread_owner")
    assert (await client.put(f"/comments/{comment_id}", json={"content": "x"})).status_code == 403
    assert (await client.delete(f"/comments/{comment_id}")).status_code == 204
    assert (await client.get("/albums/album_x/reviews")).json()[0]["comments"] == []


@pytest.mark.asyncio
async def test_comment_author_can_delete_own_comment(client):
    review_id = await _review_as(client, "c_owner", stars=4)
    await log_in_test_user(client, spotify_id="c_author")
    comment_id = (await client.post(f"/reviews/{review_id}/comments", json={"content": "oops"})).json()["id"]
    assert (await client.delete(f"/comments/{comment_id}")).status_code == 204


@pytest.mark.asyncio
async def test_unlike_review_and_comment(client):
    review_id = await _review_as(client, "u_owner", stars=4)
    await log_in_test_user(client, spotify_id="u_fan")
    comment_id = (await client.post(f"/reviews/{review_id}/comments", json={"content": "c"})).json()["id"]
    await client.post(f"/reviews/{review_id}/like")
    await client.post(f"/comments/{comment_id}/like")

    liked = (await client.get("/albums/album_x/reviews")).json()[0]
    assert liked["liked_by_me"] is True and liked["like_count"] == 1
    assert liked["comments"][0]["liked_by_me"] is True

    assert (await client.delete(f"/reviews/{review_id}/like")).status_code == 204
    assert (await client.delete(f"/comments/{comment_id}/like")).status_code == 204
    # Idempotent.
    assert (await client.delete(f"/reviews/{review_id}/like")).status_code == 204

    after = (await client.get("/albums/album_x/reviews")).json()[0]
    assert after["liked_by_me"] is False and after["like_count"] == 0
    assert after["comments"][0]["liked_by_me"] is False and after["comments"][0]["like_count"] == 0

    # And you can like again afterwards.
    assert (await client.post(f"/reviews/{review_id}/like")).status_code == 201


@pytest.mark.asyncio
async def test_unlike_only_removes_your_own_like(client):
    review_id = await _review_as(client, "ul_owner", stars=4)
    await log_in_test_user(client, spotify_id="ul_a")
    await client.post(f"/reviews/{review_id}/like")
    await log_in_test_user(client, spotify_id="ul_b")
    await client.post(f"/reviews/{review_id}/like")
    await client.delete(f"/reviews/{review_id}/like")

    assert (await client.get("/albums/album_x/reviews")).json()[0]["like_count"] == 1


@pytest.mark.asyncio
async def test_anonymous_listing_has_liked_by_me_false(client):
    review_id = await _review_as(client, "anon_owner", stars=4)
    await client.post(f"/reviews/{review_id}/like")
    client.cookies.clear()
    listed = (await client.get("/albums/album_x/reviews")).json()[0]
    assert listed["liked_by_me"] is False and listed["like_count"] == 1
