"""One-to-one conversations that start with a song recommendation.

Rules, all enforced here rather than trusted from the client:
- You can only start a conversation with someone you follow (a cheap
  anti-spam gate — strangers can't cold-message you).
- The opening message must recommend a song; after that, either side can
  send text or recommend more songs.
- Only the two participants can read or write a conversation. A
  non-participant gets the same "not found" as a missing conversation,
  so conversation ids can't be probed.
"""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.spotify_entities import Album, Artist, Track
from app.models.user import User
from app.services.profiles import UserNotFound, is_following, user_brief
from app.services.spotify_sync import ensure_track_cached, track_summary

MAX_MESSAGE_LENGTH = 2000


class NotFollowing(Exception):
    pass


class ConversationNotFound(Exception):
    pass


class EmptyMessage(Exception):
    pass


class MessageTooLong(Exception):
    pass


class CannotMessageSelf(Exception):
    pass


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _clean_body(body: str | None) -> str | None:
    if body is None:
        return None
    cleaned = body.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise MessageTooLong()
    return cleaned


async def _track_summary_by_id(db: AsyncSession, track_id: int | None) -> dict | None:
    if track_id is None:
        return None
    track = await db.get(Track, track_id)
    artist = await db.get(Artist, track.artist_id)
    album = await db.get(Album, track.album_id) if track.album_id is not None else None
    return track_summary(track, artist, album)


async def _message_dict(db: AsyncSession, message: Message) -> dict:
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "body": message.body,
        "track": await _track_summary_by_id(db, message.track_id),
        "created_at": message.created_at,
    }


async def _get_conversation_for(db: AsyncSession, user: User, conversation_id: int) -> Conversation:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or user.id not in (conversation.user_low_id, conversation.user_high_id):
        raise ConversationNotFound()
    return conversation


async def _add_message(
    db: AsyncSession, conversation: Conversation, sender: User, body: str | None, track_id: int | None
) -> Message:
    message = Message(conversation_id=conversation.id, sender_id=sender.id, body=body, track_id=track_id)
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.flush()
    return message


async def start_conversation(
    db: AsyncSession, sender: User, to_user_id: int, track_spotify_id: str, body: str | None
) -> dict:
    """Recommend a song to someone you follow. If a conversation with them
    already exists, this just adds the recommendation to it.
    """
    if to_user_id == sender.id:
        raise CannotMessageSelf()
    recipient = await db.get(User, to_user_id)
    if recipient is None:
        raise UserNotFound()
    if not await is_following(db, sender.id, to_user_id):
        raise NotFollowing()

    cleaned = _clean_body(body)
    track = await ensure_track_cached(db, track_spotify_id)

    low, high = _pair(sender.id, to_user_id)
    conversation = await db.scalar(
        select(Conversation).where(Conversation.user_low_id == low, Conversation.user_high_id == high)
    )
    if conversation is None:
        conversation = Conversation(user_low_id=low, user_high_id=high)
        db.add(conversation)
        await db.flush()

    message = await _add_message(db, conversation, sender, cleaned, track.id)
    result = {"conversation_id": conversation.id, "message": await _message_dict(db, message)}
    await db.commit()
    return result


async def send_message(
    db: AsyncSession, sender: User, conversation_id: int, body: str | None, track_spotify_id: str | None
) -> dict:
    conversation = await _get_conversation_for(db, sender, conversation_id)
    cleaned = _clean_body(body)

    track_id = None
    if track_spotify_id:
        track_id = (await ensure_track_cached(db, track_spotify_id)).id
    if cleaned is None and track_id is None:
        raise EmptyMessage()

    message = await _add_message(db, conversation, sender, cleaned, track_id)
    result = await _message_dict(db, message)
    await db.commit()
    return result


async def list_conversations(db: AsyncSession, user: User) -> list[dict]:
    conversations = await db.scalars(
        select(Conversation)
        .where(or_(Conversation.user_low_id == user.id, Conversation.user_high_id == user.id))
        .order_by(Conversation.last_message_at.desc())
    )
    results = []
    for conversation in conversations:
        other_id = conversation.user_high_id if conversation.user_low_id == user.id else conversation.user_low_id
        other = await db.get(User, other_id)
        last = await db.scalar(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id.desc()).limit(1)
        )
        results.append(
            {
                "id": conversation.id,
                "with": user_brief(other),
                "last_message": await _message_dict(db, last) if last is not None else None,
                "last_message_at": conversation.last_message_at,
            }
        )
    return results


async def get_messages(db: AsyncSession, user: User, conversation_id: int, after_id: int = 0) -> dict:
    """`after_id` lets the frontend poll cheaply: ask only for messages
    newer than the last one it already has."""
    conversation = await _get_conversation_for(db, user, conversation_id)
    other_id = conversation.user_high_id if conversation.user_low_id == user.id else conversation.user_low_id
    other = await db.get(User, other_id)

    if after_id > 0:
        rows = list(
            await db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id, Message.id > after_id)
                .order_by(Message.id)
                .limit(200)
            )
        )
    else:
        # First load: the most recent 200, oldest-first for display.
        latest = await db.scalars(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id.desc()).limit(200)
        )
        rows = list(reversed(list(latest)))
    return {
        "conversation_id": conversation.id,
        "with": user_brief(other),
        "messages": [await _message_dict(db, m) for m in rows],
    }
