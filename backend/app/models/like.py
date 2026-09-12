"""A like on either a review or a comment — same exclusive-arc pattern as
Review's target columns."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    review_id: Mapped[int | None] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"))
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(review_id, comment_id) = 1",
            name="like_exactly_one_target",
        ),
        Index("uq_like_user_review", "user_id", "review_id", unique=True, postgresql_where="review_id IS NOT NULL"),
        Index(
            "uq_like_user_comment", "user_id", "comment_id", unique=True, postgresql_where="comment_id IS NOT NULL"
        ),
    )

    user: Mapped["User"] = relationship()
