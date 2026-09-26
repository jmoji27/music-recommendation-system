"""Conversations that start with a song recommendation."""

import pytest
import respx
from sqlalchemy import select

from app.models.spotify_entities import Track
from tests.conftest import log_in_test_user
from tests.helpers import mock_catalog, user_id


async def _sender_follows_receiver(client, db_session, sender="msg_sender", receiver="msg_receiver"):
    """Leaves the client logged in as the sender, following the receiver."""
    await log_in_test_user(client, spotify_id=receiver)
    receiver_id = await user_id(db_session, receiver)
    await log_in_test_user(client, spotify_id=sender)
    await client.post(f"/users/{receiver_id}/follow")
    return await user_id(db_session, sender), receiver_id


async def _recommend(client, receiver_id, body=None):
    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        return await client.post(
            "/conversations", json={"to_user_id": receiver_id, "track_spotify_id": "track_one", "body": body}
        )


@pytest.mark.asyncio
async def test_must_follow_before_recommending(client, db_session):
    await log_in_test_user(client, spotify_id="nf_receiver")
    receiver_id = await user_id(db_session, "nf_receiver")
    await log_in_test_user(client, spotify_id="nf_sender")

    response = await _recommend(client, receiver_id)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_start_conversation_with_a_song_and_caches_the_track(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)

    response = await _recommend(client, receiver_id, body="You'll love this")
    assert response.status_code == 201
    message = response.json()["message"]
    assert message["track"]["name"] == "Song One"
    assert message["track"]["artist"]["name"] == "Artist X"
    assert message["body"] == "You'll love this"

    assert await db_session.scalar(select(Track).where(Track.spotify_id == "track_one")) is not None


@pytest.mark.asyncio
async def test_conversation_requires_a_song_to_start(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)
    response = await client.post("/conversations", json={"to_user_id": receiver_id, "body": "hey"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cannot_message_self_or_missing_user(client, db_session):
    sender_id, _ = await _sender_follows_receiver(client, db_session)
    assert (await _recommend(client, sender_id)).status_code == 400
    assert (await _recommend(client, 999999)).status_code == 404


@pytest.mark.asyncio
async def test_second_recommendation_reuses_the_same_conversation(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)
    first = (await _recommend(client, receiver_id)).json()["conversation_id"]
    second = (await _recommend(client, receiver_id)).json()["conversation_id"]
    assert first == second
    assert len((await client.get("/conversations")).json()) == 1


@pytest.mark.asyncio
async def test_receiver_sees_and_replies_without_following_back(client, db_session):
    sender_id, receiver_id = await _sender_follows_receiver(client, db_session)
    conversation_id = (await _recommend(client, receiver_id, body="listen")).json()["conversation_id"]

    await log_in_test_user(client, spotify_id="msg_receiver")
    inbox = (await client.get("/conversations")).json()
    assert [c["id"] for c in inbox] == [conversation_id]
    assert inbox[0]["with"]["id"] == sender_id
    assert inbox[0]["last_message"]["track"]["name"] == "Song One"

    reply = await client.post(f"/conversations/{conversation_id}/messages", json={"body": "Great pick!"})
    assert reply.status_code == 201

    thread = (await client.get(f"/conversations/{conversation_id}/messages")).json()
    assert [m["body"] for m in thread["messages"]] == ["listen", "Great pick!"]
    assert thread["messages"][0]["sender_id"] == sender_id
    assert thread["messages"][1]["sender_id"] == receiver_id


@pytest.mark.asyncio
async def test_strangers_cannot_read_or_write_a_conversation(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)
    conversation_id = (await _recommend(client, receiver_id)).json()["conversation_id"]

    await log_in_test_user(client, spotify_id="msg_stranger")
    assert (await client.get(f"/conversations/{conversation_id}/messages")).status_code == 404
    assert (
        await client.post(f"/conversations/{conversation_id}/messages", json={"body": "let me in"})
    ).status_code == 404
    assert (await client.get("/conversations")).json() == []


@pytest.mark.asyncio
async def test_message_validation(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)
    conversation_id = (await _recommend(client, receiver_id)).json()["conversation_id"]
    url = f"/conversations/{conversation_id}/messages"

    assert (await client.post(url, json={})).status_code == 422
    assert (await client.post(url, json={"body": "   "})).status_code == 422
    assert (await client.post(url, json={"body": "x" * 2001})).status_code == 422
    assert (await client.post(url, json={"body": "x" * 4001})).status_code == 422  # rejected by the schema
    assert (await client.post(url, json={"body": "x" * 2000})).status_code == 201


@pytest.mark.asyncio
async def test_can_recommend_another_song_inside_a_conversation(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)
    conversation_id = (await _recommend(client, receiver_id)).json()["conversation_id"]

    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        response = await client.post(
            f"/conversations/{conversation_id}/messages", json={"track_spotify_id": "track_one"}
        )
    assert response.status_code == 201
    assert response.json()["body"] is None
    assert response.json()["track"]["name"] == "Song One"


@pytest.mark.asyncio
async def test_polling_with_after_id_returns_only_newer_messages(client, db_session):
    _, receiver_id = await _sender_follows_receiver(client, db_session)
    conversation_id = (await _recommend(client, receiver_id)).json()["conversation_id"]
    url = f"/conversations/{conversation_id}/messages"
    await client.post(url, json={"body": "second"})

    everything = (await client.get(url)).json()["messages"]
    assert len(everything) == 2

    newer = (await client.get(url, params={"after_id": everything[0]["id"]})).json()["messages"]
    assert [m["body"] for m in newer] == ["second"]
    assert (await client.get(url, params={"after_id": everything[1]["id"]})).json()["messages"] == []


@pytest.mark.asyncio
async def test_track_search_endpoint_is_public_and_caches(client):
    with respx.mock(assert_all_called=False) as mock:
        mock_catalog(mock)
        response = await client.get("/catalog/tracks/search", params={"q": "song"})
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Song One"
    assert response.json()[0]["album"]["name"] == "Test Album X"


@pytest.mark.asyncio
async def test_messaging_requires_auth(client):
    assert (await client.get("/conversations")).status_code == 401
    assert (await client.post("/conversations", json={"to_user_id": 1, "track_spotify_id": "t"})).status_code == 401
