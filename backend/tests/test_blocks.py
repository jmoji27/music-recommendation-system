"""Blocking, tested through the HTTP API from both sides of a block.

Cast: alice blocks bob. carol is an uninvolved third party.
Rules under test (see app/services/blocks.py):
  - the block is a wall in both directions for follow / message / comment / like
  - each side disappears from the other's view
  - blocked-by-you says so (403); blocked-by-them looks like "not found" (404)
"""

import pytest
import pytest_asyncio
import respx

from tests.conftest import log_in_test_user
from tests.helpers import mock_catalog, user_id
from tests.test_interactions import _mock_album_lookup


async def _as(client, name: str) -> None:
    await log_in_test_user(client, spotify_id=name)


async def _review(client, name: str, **payload) -> int:
    await _as(client, name)
    with respx.mock(assert_all_called=False) as mock:
        _mock_album_lookup(mock)
        return (await client.post("/albums/album_x/reviews", json=payload)).json()["id"]


async def _recommend(client, to_id: int):
    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        return await client.post("/conversations", json={"to_user_id": to_id, "track_spotify_id": "track_one"})


@pytest_asyncio.fixture
async def world(client, db_session):
    """alice and bob follow each other, review the same album, comment on
    and like each other's reviews, and have a conversation. Nothing is
    blocked yet; the client is left logged in as alice."""
    for name in ("alice", "bob", "carol"):
        await _as(client, name)
    ids = {name: await user_id(db_session, name) for name in ("alice", "bob", "carol")}

    review = {}
    for name in ("alice", "bob", "carol"):
        review[name] = await _review(client, name, stars=4, content=f"{name} review")

    await _as(client, "bob")
    await client.post(f"/users/{ids['alice']}/follow")
    await client.post(f"/reviews/{review['alice']}/comments", json={"content": "bob on alice"})
    await client.post(f"/reviews/{review['alice']}/like")
    convo = (await _recommend(client, ids["alice"])).json()["conversation_id"]

    await _as(client, "alice")
    await client.post(f"/users/{ids['bob']}/follow")
    await client.post(f"/reviews/{review['bob']}/comments", json={"content": "alice on bob"})
    await client.post(f"/reviews/{review['bob']}/like")

    await _as(client, "carol")
    await client.post(f"/users/{ids['alice']}/follow")
    await client.post(f"/users/{ids['bob']}/follow")

    await _as(client, "alice")
    return {"ids": ids, "review": review, "convo": convo}


async def _alice_blocks_bob(client, world):
    await _as(client, "alice")
    response = await client.post(f"/users/{world['ids']['bob']}/block")
    assert response.status_code == 204


def _names(reviews) -> set[str]:
    return {r["user"]["display_name"] for r in reviews}


# ── the block itself ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_block_requires_login(client):
    assert (await client.post("/users/1/block")).status_code == 401
    assert (await client.delete("/users/1/block")).status_code == 401
    assert (await client.get("/me/blocks")).status_code == 401


@pytest.mark.asyncio
async def test_cannot_block_yourself_or_a_missing_user(client, world):
    assert (await client.post(f"/users/{world['ids']['alice']}/block")).status_code == 400
    assert (await client.post("/users/99999999/block")).status_code == 404


@pytest.mark.asyncio
async def test_block_is_idempotent_and_listed_only_for_the_blocker(client, world):
    bob = world["ids"]["bob"]
    await _alice_blocks_bob(client, world)
    assert (await client.post(f"/users/{bob}/block")).status_code == 204

    blocked = (await client.get("/me/blocks")).json()
    assert [u["id"] for u in blocked] == [bob]

    await _as(client, "bob")
    assert (await client.get("/me/blocks")).json() == []  # bob can't see that he's blocked


@pytest.mark.asyncio
async def test_blocking_removes_follows_in_both_directions(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    await client.delete(f"/users/{ids['bob']}/block")  # unblocking doesn't bring them back

    followers = (await client.get(f"/users/{ids['alice']}/followers")).json()
    following = (await client.get(f"/users/{ids['alice']}/following")).json()
    assert ids["bob"] not in {u["id"] for u in followers}
    assert ids["bob"] not in {u["id"] for u in following}
    # carol's follows are untouched
    assert ids["carol"] in {u["id"] for u in followers}


@pytest.mark.asyncio
async def test_unblock_restores_visibility_and_interaction(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    assert (await client.delete(f"/users/{ids['bob']}/block")).status_code == 204
    assert (await client.delete(f"/users/{ids['bob']}/block")).status_code == 204  # idempotent

    assert (await client.get(f"/users/{ids['bob']}")).json()["blocked_by_me"] is False
    reviews = (await client.get("/albums/album_x/reviews")).json()
    assert world["review"]["bob"] in {r["id"] for r in reviews}
    assert (await client.post(f"/users/{ids['bob']}/follow")).status_code == 204


# ── follow ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cannot_follow_across_a_block_either_way(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)

    assert (await client.post(f"/users/{ids['bob']}/follow")).status_code == 403  # blocked by you

    await _as(client, "bob")
    assert (await client.post(f"/users/{ids['alice']}/follow")).status_code == 404  # blocked by them


# ── profiles ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_blocked_user_cannot_see_the_blockers_profile(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    await _as(client, "bob")
    for path in ("", "/activity", "/followers", "/following"):
        response = await client.get(f"/users/{ids['alice']}{path}")
        assert response.status_code == 404, path


@pytest.mark.asyncio
async def test_blocker_sees_only_a_stub_profile_of_the_blocked_user(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    body = (await client.get(f"/users/{ids['bob']}")).json()
    assert body["blocked_by_me"] is True
    assert "follower_count" not in body and "review_count" not in body
    for path in ("/activity", "/followers", "/following"):
        assert (await client.get(f"/users/{ids['bob']}{path}")).status_code == 404, path


@pytest.mark.asyncio
async def test_third_party_still_sees_both_profiles(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    await _as(client, "carol")
    for name in ("alice", "bob"):
        assert (await client.get(f"/users/{ids[name]}")).status_code == 200


@pytest.mark.asyncio
async def test_anonymous_visitors_are_unaffected(client, world):
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    client.cookies.clear()
    assert (await client.get(f"/users/{ids['bob']}")).status_code == 200
    assert _names((await client.get("/albums/album_x/reviews")).json()) == {"Test User"}


@pytest.mark.asyncio
async def test_followers_lists_hide_blocked_people_from_third_parties_viewing(client, world):
    """carol looks at alice's followers: bob is gone from alice's list because
    the follow was removed, and carol still sees herself."""
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    await _as(client, "carol")
    followers = {u["id"] for u in (await client.get(f"/users/{ids['alice']}/followers")).json()}
    assert followers == {ids["carol"]}


@pytest.mark.asyncio
async def test_a_blocked_person_hidden_from_a_viewers_view_of_a_third_users_lists(client, world):
    """alice blocked bob; carol follows both. When alice views carol's
    following list, bob must not appear (and vice versa for bob)."""
    ids = world["ids"]
    await _alice_blocks_bob(client, world)
    seen_by_alice = {u["id"] for u in (await client.get(f"/users/{ids['carol']}/following")).json()}
    assert seen_by_alice == {ids["alice"]}

    await _as(client, "bob")
    seen_by_bob = {u["id"] for u in (await client.get(f"/users/{ids['carol']}/following")).json()}
    assert seen_by_bob == {ids["bob"]}


# ── search ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_hides_blocked_users_both_ways(client, world):
    await _alice_blocks_bob(client, world)
    # display_name is "Test User" for everyone in these tests; scope by id.
    ids = world["ids"]
    found_by_alice = {u["id"] for u in (await client.get("/users/search", params={"q": "Test User"})).json()}
    assert ids["bob"] not in found_by_alice and ids["carol"] in found_by_alice

    await _as(client, "bob")
    found_by_bob = {u["id"] for u in (await client.get("/users/search", params={"q": "Test User"})).json()}
    assert ids["alice"] not in found_by_bob and ids["carol"] in found_by_bob


# ── reviews, comments, likes ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_blocked_users_reviews_disappear_from_album_page_both_ways(client, world):
    await _alice_blocks_bob(client, world)

    def authors(reviews):
        return {r["id"] for r in reviews}

    mine = (await client.get("/albums/album_x/reviews")).json()
    assert world["review"]["bob"] not in authors(mine)
    assert {world["review"]["alice"], world["review"]["carol"]} <= authors(mine)

    await _as(client, "bob")
    theirs = (await client.get("/albums/album_x/reviews")).json()
    assert world["review"]["alice"] not in authors(theirs)
    assert {world["review"]["bob"], world["review"]["carol"]} <= authors(theirs)

    await _as(client, "carol")
    third = (await client.get("/albums/album_x/reviews")).json()
    assert {world["review"][n] for n in ("alice", "bob", "carol")} <= authors(third)


@pytest.mark.asyncio
async def test_blocked_users_comments_and_likes_vanish_from_the_blockers_view(client, world):
    await _alice_blocks_bob(client, world)
    mine = next(r for r in (await client.get("/albums/album_x/reviews")).json() if r["id"] == world["review"]["alice"])
    assert mine["comments"] == []  # bob's comment on alice's review
    assert mine["like_count"] == 0  # bob's like doesn't count for alice
    assert mine["liked_by_me"] is False

    await _as(client, "carol")
    third = next(r for r in (await client.get("/albums/album_x/reviews")).json() if r["id"] == world["review"]["alice"])
    assert len(third["comments"]) == 1 and third["like_count"] == 1


@pytest.mark.asyncio
async def test_cannot_comment_on_or_like_across_a_block(client, world):
    review = world["review"]
    await _alice_blocks_bob(client, world)

    # alice -> bob's review: she blocked him.
    assert (await client.post(f"/reviews/{review['bob']}/comments", json={"content": "x"})).status_code == 403
    assert (await client.post(f"/reviews/{review['bob']}/like")).status_code == 403

    # bob -> alice's review: looks like it isn't there.
    await _as(client, "bob")
    assert (await client.post(f"/reviews/{review['alice']}/comments", json={"content": "x"})).status_code == 404
    unliked = await client.delete(f"/reviews/{review['alice']}/like")
    assert unliked.status_code == 204
    assert (await client.post(f"/reviews/{review['alice']}/like")).status_code == 404


@pytest.mark.asyncio
async def test_cannot_like_a_comment_across_a_block(client, world):
    await _as(client, "carol")
    alice_review = next(r for r in (await client.get("/albums/album_x/reviews")).json() if r["id"] == world["review"]["alice"])
    bobs_comment = alice_review["comments"][0]["id"]

    await _alice_blocks_bob(client, world)
    assert (await client.post(f"/comments/{bobs_comment}/like")).status_code == 403

    await _as(client, "carol")  # uninvolved third party can still like it
    assert (await client.post(f"/comments/{bobs_comment}/like")).status_code == 201


@pytest.mark.asyncio
async def test_blockers_feed_never_shows_the_blocked_user(client, world):
    ids = world["ids"]
    await _as(client, "carol")  # follows both alice and bob
    before = (await client.get("/me/friends/feed")).json()
    assert {item["actor"]["id"] for item in before} >= {ids["alice"], ids["bob"]}

    await client.post(f"/users/{ids['bob']}/block")
    after = (await client.get("/me/friends/feed")).json()
    assert ids["bob"] not in {item["actor"]["id"] for item in after}
    assert ids["alice"] in {item["actor"]["id"] for item in after}


@pytest.mark.asyncio
async def test_feed_hides_items_touching_a_blocked_person(client, world):
    """alice's comment/like on bob's review shows in a friend's feed until
    that friend blocks bob."""
    ids = world["ids"]
    await _as(client, "carol")
    feed = (await client.get("/me/friends/feed")).json()
    assert any(item.get("review_author", {}).get("id") == ids["bob"] for item in feed)  # precondition

    await client.post(f"/users/{ids['bob']}/block")
    feed = (await client.get("/me/friends/feed")).json()
    for item in feed:
        assert item["actor"]["id"] != ids["bob"]
        assert item.get("review_author", {}).get("id") != ids["bob"]
        assert item.get("target_author", {}).get("id") != ids["bob"]


@pytest.mark.asyncio
async def test_profile_activity_hides_interactions_with_a_blocked_person(client, world):
    """carol views alice's activity after carol blocks bob: alice's comment
    on bob's review must not appear."""
    ids = world["ids"]
    await _as(client, "carol")
    activity = (await client.get(f"/users/{ids['alice']}/activity")).json()
    assert any(c["review_author"]["id"] == ids["bob"] for c in activity["comments"])

    await client.post(f"/users/{ids['bob']}/block")
    activity = (await client.get(f"/users/{ids['alice']}/activity")).json()
    assert all(c["review_author"]["id"] != ids["bob"] for c in activity["comments"])
    assert all(like["target_author"]["id"] != ids["bob"] for like in activity["likes"])


# ── messaging ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_conversation_disappears_for_both_sides_while_blocked(client, world):
    convo = world["convo"]
    assert len((await client.get("/conversations")).json()) == 1
    await _alice_blocks_bob(client, world)

    assert (await client.get("/conversations")).json() == []
    assert (await client.get(f"/conversations/{convo}/messages")).status_code == 404

    await _as(client, "bob")
    assert (await client.get("/conversations")).json() == []
    assert (await client.get(f"/conversations/{convo}/messages")).status_code == 404


@pytest.mark.asyncio
async def test_cannot_send_messages_across_a_block(client, world):
    convo, ids = world["convo"], world["ids"]
    await _alice_blocks_bob(client, world)

    assert (await client.post(f"/conversations/{convo}/messages", json={"body": "hi"})).status_code == 404
    assert (await _recommend(client, ids["bob"])).status_code == 403  # you blocked him

    await _as(client, "bob")
    assert (await client.post(f"/conversations/{convo}/messages", json={"body": "hi"})).status_code == 404
    assert (await _recommend(client, ids["alice"])).status_code == 404  # looks nonexistent


@pytest.mark.asyncio
async def test_conversation_history_returns_after_unblock(client, world):
    convo, ids = world["convo"], world["ids"]
    await _alice_blocks_bob(client, world)
    await client.delete(f"/users/{ids['bob']}/block")

    assert len((await client.get("/conversations")).json()) == 1
    messages = (await client.get(f"/conversations/{convo}/messages")).json()["messages"]
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_third_party_conversations_are_unaffected(client, world):
    ids = world["ids"]
    await _as(client, "carol")
    await client.post(f"/users/{ids['alice']}/follow")
    assert (await _recommend(client, ids["alice"])).status_code == 201
    await _alice_blocks_bob(client, world)
    await _as(client, "carol")
    assert len((await client.get("/conversations")).json()) == 1


@pytest.mark.asyncio
async def test_third_users_followers_list_hides_people_you_are_blocked_with(client, world):
    """alice and bob both follow carol. Once alice blocks bob, neither sees
    the other in carol's followers list."""
    ids = world["ids"]
    await client.post(f"/users/{ids['carol']}/follow")
    await _as(client, "bob")
    await client.post(f"/users/{ids['carol']}/follow")
    await _alice_blocks_bob(client, world)

    seen_by_alice = {u["id"] for u in (await client.get(f"/users/{ids['carol']}/followers")).json()}
    assert seen_by_alice == {ids["alice"]}
    await _as(client, "bob")
    seen_by_bob = {u["id"] for u in (await client.get(f"/users/{ids['carol']}/followers")).json()}
    assert seen_by_bob == {ids["bob"]}
