"""One-to-one conversations. A conversation between two people is
created by recommending a song to them — the first message must carry
a track (enforced in the service layer, since "first message" isn't
something a CHECK constraint can express) — after which either side can
send plain text or more recommendations.

The pair is stored ordered (low id, high id) with a unique constraint,
so there can only ever be one conversation per pair regardless of who
started it.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("user_low_id < user_high_id", name="conversation_pair_ordered"),
        UniqueConstraint("user_low_id", "user_high_id", name="uq_conversation_pair"),
        Index("ix_conversation_high", "user_high_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str | None] = mapped_column(Text)
    # RESTRICT for the same reason as interactions: the cache-retention
    # job must never be able to silently delete a track someone was sent.
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("body IS NOT NULL OR track_id IS NOT NULL", name="message_has_content"),
        Index("ix_message_conversation_created", "conversation_id", "created_at"),
    )
