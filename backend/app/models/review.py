"""A Letterboxd-style "log entry": a user rating and/or reviewing exactly
one of an artist, album, or track.

Exclusive-arc design: artist_id/album_id/track_id are all nullable FKs,
enforced by a CHECK constraint to have exactly one set. This keeps real
referential integrity (unlike a generic entity_type/entity_id pair) at the
cost of a few unused columns per row.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    artist_id: Mapped[int | None] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"))
    album_id: Mapped[int | None] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"))
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))

    # 1-5 stars; a log entry needs at least a rating or a body (enforced
    # by CHECK below), matching Letterboxd's "you can just log, or log +
    # write about it" behavior.
    stars: Mapped[int | None] = mapped_column(SmallInteger)
    body: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(artist_id, album_id, track_id) = 1",
            name="review_exactly_one_target",
        ),
        CheckConstraint(
            "stars IS NOT NULL OR body IS NOT NULL",
            name="review_has_stars_or_body",
        ),
        CheckConstraint("stars IS NULL OR stars BETWEEN 1 AND 5", name="review_stars_range"),
        Index("uq_review_user_artist", "user_id", "artist_id", unique=True, postgresql_where="artist_id IS NOT NULL"),
        Index("uq_review_user_album", "user_id", "album_id", unique=True, postgresql_where="album_id IS NOT NULL"),
        Index("uq_review_user_track", "user_id", "track_id", unique=True, postgresql_where="track_id IS NOT NULL"),
    )

    user: Mapped["User"] = relationship()
