"""Blocking, enforced here in the service layer — never in the frontend.

A block is a wall in both directions. While either of two people has
blocked the other:
  - neither can follow, message, comment on, or like the other;
  - each is invisible to the other: their reviews, comments, likes, profile,
    follower lists, search results and conversations disappear.

The two sides get deliberately different errors, so blocking someone
doesn't tell them they've been blocked:
  - BlockedByYou  -> 403 "unblock them first" (you know; it's your block)
  - BlockedByThem -> 404 "not found" (indistinguishable from the person
    not existing)

Every path that lets one user reach another user's data or account goes
through `assert_no_block` or `hidden_user_ids`; tests/test_blocks.py
exercises each of those paths through the HTTP API.
"""

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.follow import Follow
from app.models.user import User


class BlockedByYou(Exception):
    pass


class BlockedByThem(Exception):
    pass


class CannotBlockSelf(Exception):
    pass


class UserNotFound(Exception):
    pass


async def hidden_user_ids(db: AsyncSession, user_id: int) -> set[int]:
    """Everyone `user_id` shouldn't see or interact with: people they
    blocked plus people who blocked them."""
    rows = await db.execute(
        select(Block.blocker_id, Block.blocked_id).where(or_(Block.blocker_id == user_id, Block.blocked_id == user_id))
    )
    hidden: set[int] = set()
    for blocker_id, blocked_id in rows:
        hidden.add(blocked_id if blocker_id == user_id else blocker_id)
    return hidden


async def hidden_for(db: AsyncSession, viewer: User | None) -> set[int]:
    """`hidden_user_ids` for an optional viewer; anonymous visitors hide nothing."""
    return set() if viewer is None else await hidden_user_ids(db, viewer.id)


async def assert_no_block(db: AsyncSession, actor: User, other_id: int) -> None:
    """Raises if there's a block between `actor` and `other_id`, in either direction."""
    if other_id == actor.id:
        return
    rows = await db.execute(
        select(Block.blocker_id).where(
            or_(
                (Block.blocker_id == actor.id) & (Block.blocked_id == other_id),
                (Block.blocker_id == other_id) & (Block.blocked_id == actor.id),
            )
        )
    )
    blockers = set(rows.scalars())
    if actor.id in blockers:
        raise BlockedByYou()
    if other_id in blockers:
        raise BlockedByThem()


async def block_user(db: AsyncSession, blocker: User, target_id: int) -> None:
    if target_id == blocker.id:
        raise CannotBlockSelf()
    if await db.get(User, target_id) is None:
        raise UserNotFound()

    db.add(Block(blocker_id=blocker.id, blocked_id=target_id))
    try:
        await db.flush()
    except IntegrityError:
        # Already blocked — idempotent.
        await db.rollback()
        return
    # Follows in both directions end with the block and don't come back on unblock.
    await db.execute(
        delete(Follow).where(
            or_(
                (Follow.follower_id == blocker.id) & (Follow.followed_id == target_id),
                (Follow.follower_id == target_id) & (Follow.followed_id == blocker.id),
            )
        )
    )
    await db.commit()


async def unblock_user(db: AsyncSession, blocker: User, target_id: int) -> None:
    await db.execute(delete(Block).where(Block.blocker_id == blocker.id, Block.blocked_id == target_id))
    await db.commit()


async def is_blocked_by(db: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    return (
        await db.scalar(select(Block).where(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id))
    ) is not None


async def list_blocked(db: AsyncSession, blocker: User) -> list[User]:
    """People *you* blocked — never the reverse."""
    rows = await db.scalars(
        select(User).join(Block, Block.blocked_id == User.id).where(Block.blocker_id == blocker.id).order_by(Block.created_at.desc())
    )
    return list(rows)
