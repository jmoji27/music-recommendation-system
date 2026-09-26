"""Review/comment/like logic on top of the single `interactions` table.

See app/models/interaction.py for the schema rationale (exclusive-arc
targets, review vs. comment/like shapes). This module is what actually
creates and lists rows in it.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction, InteractionType
from app.models.spotify_entities import Album
from app.models.user import User
from app.services import blocks
from app.services.spotify_sync import ensure_album_cached


class AlreadyReviewed(Exception):
    pass


class AlreadyLiked(Exception):
    pass


class TargetNotFound(Exception):
    pass


class NotAllowed(Exception):
    """The target exists but this user may not change it."""


def _edited(row: Interaction) -> bool:
    # created_at and updated_at both default to the creating transaction's
    # now(); only an UPDATE (via onupdate) moves updated_at past it.
    return row.updated_at is not None and row.updated_at > row.created_at


async def _liked_ids(db: AsyncSession, viewer: User | None, target_ids: list[int]) -> set[int]:
    if viewer is None or not target_ids:
        return set()
    rows = await db.scalars(
        select(Interaction.parent_interaction_id).where(
            Interaction.type == InteractionType.LIKE,
            Interaction.user_id == viewer.id,
            Interaction.parent_interaction_id.in_(target_ids),
        )
    )
    return set(rows)


def _user_summary(user: User) -> dict:
    return {"id": user.id, "display_name": user.display_name}


async def _like_count(db: AsyncSession, parent_interaction_id: int, hidden: set[int] = frozenset()) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Interaction)
        .where(
            Interaction.type == InteractionType.LIKE,
            Interaction.parent_interaction_id == parent_interaction_id,
            Interaction.user_id.not_in(hidden),
        )
    )


async def _comment_summaries(
    db: AsyncSession, review_id: int, viewer: User | None = None, hidden: set[int] = frozenset()
) -> list[dict]:
    comments = await db.scalars(
        select(Interaction)
        .where(
            Interaction.type == InteractionType.COMMENT,
            Interaction.parent_interaction_id == review_id,
            Interaction.user_id.not_in(hidden),
        )
        .order_by(Interaction.created_at)
    )
    comments = list(comments)
    liked = await _liked_ids(db, viewer, [c.id for c in comments])
    results = []
    for comment in comments:
        author = await db.get(User, comment.user_id)
        results.append(
            {
                "id": comment.id,
                "content": comment.content,
                "created_at": comment.created_at,
                "edited": _edited(comment),
                "user": _user_summary(author),
                "like_count": await _like_count(db, comment.id, hidden),
                "liked_by_me": comment.id in liked,
            }
        )
    return results


async def _review_summary(
    db: AsyncSession, review: Interaction, author: User, viewer: User | None = None, hidden: set[int] = frozenset()
) -> dict:
    return {
        "id": review.id,
        "stars": review.stars,
        "content": review.content,
        "created_at": review.created_at,
        "edited": _edited(review),
        "user": _user_summary(author),
        "like_count": await _like_count(db, review.id, hidden),
        "liked_by_me": review.id in await _liked_ids(db, viewer, [review.id]),
        "comments": await _comment_summaries(db, review.id, viewer, hidden),
    }


async def create_album_review(
    db: AsyncSession, user: User, spotify_album_id: str, stars: int | None, content: str | None
) -> dict:
    album = await ensure_album_cached(db, spotify_album_id)

    review = Interaction(user_id=user.id, type=InteractionType.REVIEW, album_id=album.id, stars=stars, content=content)
    db.add(review)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AlreadyReviewed() from exc

    result = {
        "id": review.id,
        "stars": review.stars,
        "content": review.content,
        "created_at": review.created_at,
        "edited": False,
        "user": _user_summary(user),
        "like_count": 0,
        "liked_by_me": False,
        "comments": [],
    }
    await db.commit()
    return result


async def list_album_reviews(db: AsyncSession, spotify_album_id: str, viewer: User | None = None) -> list[dict]:
    album = await db.scalar(select(Album).where(Album.spotify_id == spotify_album_id))
    if album is None:
        return []

    hidden = await blocks.hidden_for(db, viewer)
    reviews = await db.scalars(
        select(Interaction)
        .where(
            Interaction.type == InteractionType.REVIEW,
            Interaction.album_id == album.id,
            Interaction.user_id.not_in(hidden),
        )
        .order_by(Interaction.created_at.desc())
    )

    results = []
    for review in reviews:
        author = await db.get(User, review.user_id)
        results.append(await _review_summary(db, review, author, viewer, hidden))
    return results


async def get_conversations_for_albums(
    db: AsyncSession, spotify_album_ids: list[str], viewer: User | None = None
) -> list[dict]:
    """Given a list of album spotify_ids (e.g. the user's own top
    albums), returns only the ones that already have reviews/comments in
    our database, each with its full review thread — "what are people
    saying about the albums you listen to most."
    """
    conversations = []
    for spotify_album_id in spotify_album_ids:
        reviews = await list_album_reviews(db, spotify_album_id, viewer)
        if reviews:
            conversations.append({"spotify_album_id": spotify_album_id, "reviews": reviews})
    return conversations


async def create_comment(db: AsyncSession, user: User, review_id: int, content: str) -> dict:
    review = await db.get(Interaction, review_id)
    if review is None or review.type != InteractionType.REVIEW:
        raise TargetNotFound()
    await blocks.assert_no_block(db, user, review.user_id)

    comment = Interaction(user_id=user.id, type=InteractionType.COMMENT, parent_interaction_id=review.id, content=content)
    db.add(comment)
    await db.flush()

    result = {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at,
        "edited": False,
        "user": _user_summary(user),
        "like_count": 0,
        "liked_by_me": False,
    }
    await db.commit()
    return result


async def like_interaction(db: AsyncSession, user: User, target_id: int, expected_type: InteractionType) -> dict:
    target = await db.get(Interaction, target_id)
    if target is None or target.type != expected_type:
        raise TargetNotFound()
    await blocks.assert_no_block(db, user, target.user_id)

    like = Interaction(user_id=user.id, type=InteractionType.LIKE, parent_interaction_id=target.id)
    db.add(like)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AlreadyLiked() from exc

    result = {"id": like.id, "target_id": target_id}
    await db.commit()
    return result


async def _get_owned(db: AsyncSession, user: User, interaction_id: int, expected_type: InteractionType) -> Interaction:
    row = await db.get(Interaction, interaction_id)
    if row is None or row.type != expected_type:
        raise TargetNotFound()
    if row.user_id != user.id:
        raise NotAllowed()
    return row


async def edit_review(db: AsyncSession, user: User, review_id: int, stars: int | None, content: str | None) -> dict:
    """Replaces the review's stars and content wholesale (PUT semantics), so
    sending `stars: null` clears the rating — the schema's CHECK still
    guarantees at least one of the two remains."""
    review = await _get_owned(db, user, review_id, InteractionType.REVIEW)
    review.stars = stars
    review.content = content
    review.updated_at = func.clock_timestamp()
    await db.flush()
    await db.refresh(review)
    result = await _review_summary(db, review, user, user)
    await db.commit()
    return result


async def delete_review(db: AsyncSession, user: User, review_id: int) -> None:
    review = await _get_owned(db, user, review_id, InteractionType.REVIEW)
    # Comments and likes hang off the review with ON DELETE CASCADE.
    await db.delete(review)
    await db.commit()


async def edit_comment(db: AsyncSession, user: User, comment_id: int, content: str) -> dict:
    comment = await _get_owned(db, user, comment_id, InteractionType.COMMENT)
    comment.content = content
    comment.updated_at = func.clock_timestamp()
    await db.flush()
    await db.refresh(comment)
    result = {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at,
        "edited": _edited(comment),
        "user": _user_summary(user),
        "like_count": await _like_count(db, comment.id),
        "liked_by_me": comment.id in await _liked_ids(db, user, [comment.id]),
    }
    await db.commit()
    return result


async def delete_comment(db: AsyncSession, user: User, comment_id: int) -> None:
    """The comment's author can delete it, and so can the author of the
    review it's on (moderating their own thread)."""
    comment = await db.get(Interaction, comment_id)
    if comment is None or comment.type != InteractionType.COMMENT:
        raise TargetNotFound()
    if comment.user_id != user.id:
        review = await db.get(Interaction, comment.parent_interaction_id)
        if review is None or review.user_id != user.id:
            raise NotAllowed()
    await db.delete(comment)
    await db.commit()


async def unlike_interaction(db: AsyncSession, user: User, target_id: int, expected_type: InteractionType) -> None:
    """Idempotent: unliking something you haven't liked is a no-op."""
    target = await db.get(Interaction, target_id)
    if target is None or target.type != expected_type:
        raise TargetNotFound()
    like = await db.scalar(
        select(Interaction).where(
            Interaction.type == InteractionType.LIKE,
            Interaction.user_id == user.id,
            Interaction.parent_interaction_id == target_id,
        )
    )
    if like is not None:
        await db.delete(like)
        await db.commit()
