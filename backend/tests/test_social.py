"""Profiles, follows, avatars, and the friends activity feed."""

import pytest
import respx

from tests.conftest import log_in_test_user
from tests.helpers import JPEG, PNG, mock_catalog, user_id


async def _two_users(client, db_session):
    await log_in_test_user(client, spotify_id="social_a")
    await log_in_test_user(client, spotify_id="social_b")  # now acting as B
    return await user_id(db_session, "social_a"), await user_id(db_session, "social_b")


@pytest.mark.asyncio
async def test_follow_unfollow_and_counts(client, db_session):
    a_id, b_id = await _two_users(client, db_session)

    assert (await client.post(f"/users/{a_id}/follow")).status_code == 204
    assert (await client.post(f"/users/{a_id}/follow")).status_code == 204  # idempotent

    profile = (await client.get(f"/users/{a_id}")).json()
    assert profile["follower_count"] == 1
    assert profile["is_following"] is True
    assert profile["is_me"] is False

    followers = (await client.get(f"/users/{a_id}/followers")).json()
    assert [u["id"] for u in followers] == [b_id]
    following = (await client.get(f"/users/{b_id}/following")).json()
    assert [u["id"] for u in following] == [a_id]

    assert (await client.delete(f"/users/{a_id}/follow")).status_code == 204
    assert (await client.get(f"/users/{a_id}")).json()["follower_count"] == 0


@pytest.mark.asyncio
async def test_cannot_follow_self_or_missing_user(client, db_session):
    _, b_id = await _two_users(client, db_session)
    assert (await client.post(f"/users/{b_id}/follow")).status_code == 400
    assert (await client.post("/users/999999/follow")).status_code == 404


@pytest.mark.asyncio
async def test_follow_requires_auth_but_profile_is_public(client, db_session):
    await log_in_test_user(client, spotify_id="social_pub")
    pub_id = await user_id(db_session, "social_pub")
    await client.post("/auth/spotify/logout")

    assert (await client.post(f"/users/{pub_id}/follow")).status_code == 401
    anonymous = await client.get(f"/users/{pub_id}")
    assert anonymous.status_code == 200
    assert anonymous.json()["is_following"] is False


@pytest.mark.asyncio
async def test_user_search_excludes_self_and_treats_wildcards_literally(client, db_session):
    await log_in_test_user(client, spotify_id="findme_one")
    await log_in_test_user(client, spotify_id="findme_two")

    results = (await client.get("/users/search", params={"q": "Test"})).json()
    assert results, "both test users are named 'Test User'"
    me = (await client.get("/me")).json()["id"]
    assert me not in [u["id"] for u in results]

    # A bare "%" must not match everything.
    assert (await client.get("/users/search", params={"q": "%"})).json() == []


@pytest.mark.asyncio
async def test_update_display_name(client, db_session):
    await log_in_test_user(client, spotify_id="rename_me")
    ok = await client.patch("/me", json={"display_name": "  New Name  "})
    assert ok.status_code == 200
    assert ok.json()["display_name"] == "New Name"

    assert (await client.patch("/me", json={"display_name": "   "})).status_code == 422
    assert (await client.patch("/me", json={"display_name": "x" * 51})).status_code == 422


@pytest.mark.asyncio
async def test_avatar_upload_serve_and_remove(client, db_session):
    await log_in_test_user(client, spotify_id="avatar_user")
    me = (await client.get("/me")).json()
    provider_avatar = me["avatar"]

    uploaded = await client.put("/me/avatar", content=PNG, headers={"Content-Type": "image/png"})
    assert uploaded.status_code == 200
    assert uploaded.json()["avatar"] == f"/users/{me['id']}/avatar"

    served = await client.get(f"/users/{me['id']}/avatar")
    assert served.status_code == 200
    assert served.content == PNG
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"

    removed = await client.delete("/me/avatar")
    assert removed.json()["avatar"] == provider_avatar
    assert (await client.get(f"/users/{me['id']}/avatar")).status_code == 404


@pytest.mark.asyncio
async def test_avatar_type_comes_from_bytes_not_client_header(client, db_session):
    await log_in_test_user(client, spotify_id="avatar_liar")
    me_id = (await client.get("/me")).json()["id"]

    # Claims PNG, is actually JPEG — must be served as what it really is.
    await client.put("/me/avatar", content=JPEG, headers={"Content-Type": "image/png"})
    assert (await client.get(f"/users/{me_id}/avatar")).headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_avatar_rejects_non_images_svg_and_oversize(client, db_session):
    await log_in_test_user(client, spotify_id="avatar_bad")

    not_image = await client.put("/me/avatar", content=b"just some text", headers={"Content-Type": "image/png"})
    assert not_image.status_code == 422

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert (await client.put("/me/avatar", content=svg, headers={"Content-Type": "image/svg+xml"})).status_code == 422

    too_big = PNG + b"0" * (200 * 1024)
    assert (await client.put("/me/avatar", content=too_big, headers={"Content-Type": "image/png"})).status_code == 413


@pytest.mark.asyncio
async def test_avatar_upload_requires_auth(client):
    assert (await client.put("/me/avatar", content=PNG)).status_code == 401


@pytest.mark.asyncio
async def test_activity_and_friends_feed(client, db_session):
    # A reviews + comments + likes; B follows A and should see it in the
    # feed; C (not followed) must not appear.
    await log_in_test_user(client, spotify_id="feed_a")
    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        review = await client.post("/albums/album_x/reviews", json={"stars": 5, "content": "Great record."})
    review_id = review.json()["id"]
    await client.post(f"/reviews/{review_id}/comments", json={"content": "Still holds up."})
    await client.post(f"/reviews/{review_id}/like")
    a_id = await user_id(db_session, "feed_a")

    await log_in_test_user(client, spotify_id="feed_c")
    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        await client.post("/albums/album_x/reviews", json={"stars": 1, "content": "Stranger's take."})

    await log_in_test_user(client, spotify_id="feed_b")
    await client.post(f"/users/{a_id}/follow")

    feed = (await client.get("/me/friends/feed")).json()
    assert {item["type"] for item in feed} == {"review", "comment", "like"}
    assert all(item["actor"]["id"] == a_id for item in feed)
    assert all(item["album"]["spotify_id"] == "album_x" for item in feed)
    assert "Stranger's take." not in str(feed)

    activity = (await client.get(f"/users/{a_id}/activity")).json()
    assert activity["reviews"][0]["content"] == "Great record."
    assert activity["comments"][0]["content"] == "Still holds up."
    assert activity["likes"][0]["target_type"] == "review"
    assert activity["likes"][0]["album"]["spotify_id"] == "album_x"


@pytest.mark.asyncio
async def test_friends_feed_empty_when_following_nobody(client):
    await log_in_test_user(client, spotify_id="lonely")
    assert (await client.get("/me/friends/feed")).json() == []


@pytest.mark.asyncio
async def test_production_requires_custom_header_on_unsafe_methods(client, db_session, monkeypatch):
    await log_in_test_user(client, spotify_id="csrf_target")
    target_id = await user_id(db_session, "csrf_target")
    await log_in_test_user(client, spotify_id="csrf_victim")

    monkeypatch.setattr("app.main.settings.environment", "production")

    # A cross-site form/simple request can't add a custom header.
    assert (await client.post(f"/users/{target_id}/follow")).status_code == 403
    assert (await client.get(f"/users/{target_id}")).status_code == 200  # reads unaffected

    ok = await client.post(f"/users/{target_id}/follow", headers={"X-Requested-With": "fetch"})
    assert ok.status_code == 204
