"""`blocker` has blocked `blocked`. One directed row per block; the service
layer (app/services/blocks.py) treats it as a wall in *both* directions.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Block(Base):
    __tablename__ = "blocks"

    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("blocker_id != blocked_id", name="block_no_self_block"),
        # "Who has blocked me?" is asked on every request that filters content.
        Index("ix_block_blocked", "blocked_id"),
    )
