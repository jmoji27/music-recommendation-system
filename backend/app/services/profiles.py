"""Profiles, follows, avatars, and the activity items shown on profiles
and in the friends feed.

"Friends" here means people you follow (the Letterboxd model) — there's
no mutual-request step.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.models.follow import Follow
from app.models.interaction import Interaction, InteractionType
from app.models.spotify_entities import Album, Artist
from app.models.user import User
from app.services.spotify_sync import album_summary

MAX_AVATAR_BYTES = 200 * 1024
MAX_DISPLAY_NAME = 50


class UserNotFound(Exception):
    pass


class CannotFollowSelf(Exception):
    pass


class InvalidImage(Exception):
    pass


class InvalidDisplayName(Exception):
    pass


def avatar_ref(user: User) -> str | None:
    """A custom upload wins over the Spotify/Google photo. Returned as a
    path ("/users/5/avatar") when custom — the frontend prefixes its API
    base — or the provider's absolute URL otherwise.
    """
    if user.has_custom_avatar:
        return f"/users/{user.id}/avatar"
    return user.avatar_url


def user_brief(user: User) -> dict:
    return {"id": user.id, "display_name": user.display_name, "avatar": avatar_ref(user)}


def sniff_image_type(data: bytes) -> str | None:
    """Trust the bytes, not the client's claimed Content-Type. SVG is
    deliberately unsupported (it can carry script)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def _get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFound()
    return user


async def _count(db: AsyncSession, stmt) -> int:
    return await db.scalar(stmt) or 0


async def get_profile(db: AsyncSession, user_id: int, viewer: User | None) -> dict:
    user = await _get_user(db, user_id)

    followers = await _count(db, select(func.count()).select_from(Follow).where(Follow.followed_id == user_id))
    following = await _count(db, select(func.count()).select_from(Follow).where(Follow.follower_id == user_id))
    reviews = await _count(
        db,
        select(func.count())
        .select_from(Interaction)
        .where(Interaction.user_id == user_id, Interaction.type == InteractionType.REVIEW),
    )

    is_following = False
    if viewer is not None and viewer.id != user_id:
        is_following = (
            await db.scalar(
                select(Follow).where(Follow.follower_id == viewer.id, Follow.followed_id == user_id)
            )
        ) is not None

    profile = user_brief(user)
    profile.update(
        {
            "follower_count": followers,
            "following_count": following,
            "review_count": reviews,
            "is_following": is_following,
            "is_me": viewer is not None and viewer.id == user_id,
            "joined_at": user.created_at,
        }
    )
    return profile


async def update_display_name(db: AsyncSession, user: User, display_name: str) -> None:
    cleaned = display_name.strip()
    if not cleaned or len(cleaned) > MAX_DISPLAY_NAME:
        raise InvalidDisplayName()
    user.display_name = cleaned
    await db.commit()


async def set_avatar(db: AsyncSession, user: User, data: bytes) -> None:
    content_type = sniff_image_type(data)
    if content_type is None or not data or len(data) > MAX_AVATAR_BYTES:
        raise InvalidImage()
    user.avatar_data = data
    user.avatar_content_type = content_type
    await db.commit()


async def clear_avatar(db: AsyncSession, user: User) -> None:
    user.avatar_data = None
    user.avatar_content_type = None
    await db.commit()


async def get_avatar(db: AsyncSession, user_id: int) -> tuple[bytes, str] | None:
    user = await db.scalar(select(User).options(undefer(User.avatar_data)).where(User.id == user_id))
    if user is None or user.avatar_data is None or user.avatar_content_type is None:
        return None
    return user.avatar_data, user.avatar_content_type


async def follow(db: AsyncSession, follower: User, target_id: int) -> None:
    if follower.id == target_id:
        raise CannotFollowSelf()
    await _get_user(db, target_id)
    db.add(Follow(follower_id=follower.id, followed_id=target_id))
    try:
        await db.commit()
    except IntegrityError:
        # Already following — idempotent, not an error.
        await db.rollback()


async def unfollow(db: AsyncSession, follower: User, target_id: int) -> None:
    existing = await db.scalar(select(Follow).where(Follow.follower_id == follower.id, Follow.followed_id == target_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def is_following(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    return (
        await db.scalar(select(Follow).where(Follow.follower_id == follower_id, Follow.followed_id == followed_id))
    ) is not None


async def list_followers(db: AsyncSession, user_id: int) -> list[dict]:
    await _get_user(db, user_id)
    users = await db.scalars(
        select(User).join(Follow, Follow.follower_id == User.id).where(Follow.followed_id == user_id).order_by(Follow.created_at.desc())
    )
    return [user_brief(u) for u in users]


async def list_following(db: AsyncSession, user_id: int) -> list[dict]:
    await _get_user(db, user_id)
    users = await db.scalars(
        select(User).join(Follow, Follow.followed_id == User.id).where(Follow.follower_id == user_id).order_by(Follow.created_at.desc())
    )
    return [user_brief(u) for u in users]


async def search_users(db: AsyncSession, query: str, viewer: User, limit: int = 20) -> list[dict]:
    cleaned = query.strip()
    if not cleaned:
        return []
    # Escape LIKE wildcards so a search for "100%" is literal.
    escaped = cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    users = await db.scalars(
        select(User)
        .where(User.display_name.ilike(f"%{escaped}%", escape="\\"), User.id != viewer.id)
        .order_by(User.display_name)
        .limit(limit)
    )
    results = []
    for user in users:
        brief = user_brief(user)
        brief["is_following"] = await is_following(db, viewer.id, user.id)
        results.append(brief)
    return results


# ── Activity ────────────────────────────────────────────────────────────


async def _album_summary_by_id(db: AsyncSession, album_id: int | None) -> dict | None:
    if album_id is None:
        return None
    album = await db.get(Album, album_id)
    if album is None:
        return None
    artist = await db.get(Artist, album.artist_id)
    return album_summary(album, artist)


def _excerpt(text: str | None, limit: int = 140) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def activity_item(db: AsyncSession, it: Interaction, actor: User | None = None) -> dict:
    """One row of "someone did something": a review, a comment on a
    review, or a like on a review/comment — always resolved back to the
    album it's about so the UI can link to it.
    """
    item: dict = {"id": it.id, "type": it.type.value, "created_at": it.created_at}
    if actor is not None:
        item["actor"] = user_brief(actor)

    if it.type == InteractionType.REVIEW:
        item.update(
            {"stars": it.stars, "content": it.content, "album": await _album_summary_by_id(db, it.album_id)}
        )
        return item

    parent = await db.get(Interaction, it.parent_interaction_id)
    if it.type == InteractionType.COMMENT:
        author = await db.get(User, parent.user_id)
        item.update(
            {
                "content": it.content,
                "review_id": parent.id,
                "review_author": user_brief(author),
                "album": await _album_summary_by_id(db, parent.album_id),
            }
        )
        return item

    # LIKE: the target is a review or a comment; a comment's album is one hop further up.
    review = parent if parent.type == InteractionType.REVIEW else await db.get(Interaction, parent.parent_interaction_id)
    target_author = await db.get(User, parent.user_id)
    item.update(
        {
            "target_type": parent.type.value,
            "target_excerpt": _excerpt(parent.content),
            "target_author": user_brief(target_author),
            "album": await _album_summary_by_id(db, review.album_id),
        }
    )
    return item


async def get_user_activity(db: AsyncSession, user_id: int, limit: int = 30) -> dict:
    await _get_user(db, user_id)
    result: dict[str, list[dict]] = {}
    for key, kind in (("reviews", InteractionType.REVIEW), ("comments", InteractionType.COMMENT), ("likes", InteractionType.LIKE)):
        rows = await db.scalars(
            select(Interaction)
            .where(Interaction.user_id == user_id, Interaction.type == kind)
            .order_by(Interaction.created_at.desc())
            .limit(limit)
        )
        result[key] = [await activity_item(db, row) for row in rows]
    return result


async def get_friends_feed(db: AsyncSession, user: User, limit: int = 40) -> list[dict]:
    """Recent reviews/comments/likes from people you follow, newest first."""
    rows = await db.execute(
        select(Interaction, User)
        .join(User, User.id == Interaction.user_id)
        .join(Follow, Follow.followed_id == Interaction.user_id)
        .where(Follow.follower_id == user.id)
        .order_by(Interaction.created_at.desc())
        .limit(limit)
    )
    return [await activity_item(db, interaction, actor) for interaction, actor in rows.all()]
