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
from app.services.spotify_sync import ensure_album_cached


class AlreadyReviewed(Exception):
    pass


class AlreadyLiked(Exception):
    pass


class TargetNotFound(Exception):
    pass


def _user_summary(user: User) -> dict:
    return {"id": user.id, "display_name": user.display_name}


async def _like_count(db: AsyncSession, parent_interaction_id: int) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Interaction)
        .where(Interaction.type == InteractionType.LIKE, Interaction.parent_interaction_id == parent_interaction_id)
    )


async def _comment_summaries(db: AsyncSession, review_id: int) -> list[dict]:
    comments = await db.scalars(
        select(Interaction)
        .where(Interaction.type == InteractionType.COMMENT, Interaction.parent_interaction_id == review_id)
        .order_by(Interaction.created_at)
    )
    results = []
    for comment in comments:
        author = await db.get(User, comment.user_id)
        results.append(
            {
                "id": comment.id,
                "content": comment.content,
                "created_at": comment.created_at,
                "user": _user_summary(author),
                "like_count": await _like_count(db, comment.id),
            }
        )
    return results


async def _review_summary(db: AsyncSession, review: Interaction, author: User) -> dict:
    return {
        "id": review.id,
        "stars": review.stars,
        "content": review.content,
        "created_at": review.created_at,
        "user": _user_summary(author),
        "like_count": await _like_count(db, review.id),
        "comments": await _comment_summaries(db, review.id),
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
        "user": _user_summary(user),
        "like_count": 0,
        "comments": [],
    }
    await db.commit()
    return result


async def list_album_reviews(db: AsyncSession, spotify_album_id: str) -> list[dict]:
    album = await db.scalar(select(Album).where(Album.spotify_id == spotify_album_id))
    if album is None:
        return []

    reviews = await db.scalars(
        select(Interaction)
        .where(Interaction.type == InteractionType.REVIEW, Interaction.album_id == album.id)
        .order_by(Interaction.created_at.desc())
    )

    results = []
    for review in reviews:
        author = await db.get(User, review.user_id)
        results.append(await _review_summary(db, review, author))
    return results


async def create_comment(db: AsyncSession, user: User, review_id: int, content: str) -> dict:
    review = await db.get(Interaction, review_id)
    if review is None or review.type != InteractionType.REVIEW:
        raise TargetNotFound()

    comment = Interaction(user_id=user.id, type=InteractionType.COMMENT, parent_interaction_id=review.id, content=content)
    db.add(comment)
    await db.flush()

    result = {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at,
        "user": _user_summary(user),
        "like_count": 0,
    }
    await db.commit()
    return result


async def like_interaction(db: AsyncSession, user: User, target_id: int, expected_type: InteractionType) -> dict:
    target = await db.get(Interaction, target_id)
    if target is None or target.type != expected_type:
        raise TargetNotFound()

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
