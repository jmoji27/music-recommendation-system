"""Every user action on the social layer — rating/reviewing an artist,
album, or track; commenting on a review; liking a review or a comment —
lives in this one table, discriminated by `type`.

Two different row "shapes" coexist here, both enforced by CHECK
constraints rather than separate tables:

- type='review': a top-level entry. Targets exactly one of
  artist_id/album_id/track_id (exclusive arc). Has stars and/or content
  (Letterboxd-style: you can just log a rating, or write about it too).
  parent_interaction_id is NULL.

- type IN ('comment', 'like'): a reply. Targets the review (or another
  comment, for likes) via parent_interaction_id, NOT the music entity
  directly — you're commenting on/liking someone's specific take, the
  same way Letterboxd works. artist_id/album_id/track_id are all NULL.
  'comment' requires content; 'like' has none.

Collapsing these into one table (instead of separate reviews/comments/
likes tables) means a feed query is one table scan instead of a UNION
across three.
"""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class InteractionType(str, enum.Enum):
    REVIEW = "review"
    COMMENT = "comment"
    LIKE = "like"


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # values_callable: SQLAlchemy's Enum type defaults to persisting a
    # Python enum member's *name* (e.g. "REVIEW"), not its *value*
    # ("review") — but the Postgres enum type (created in the migration)
    # only has the lowercase values. Without this, every insert fails
    # with "invalid input value for enum interaction_type".
    type: Mapped[InteractionType] = mapped_column(
        Enum(InteractionType, name="interaction_type", values_callable=lambda enum_cls: [member.value for member in enum_cls])
    )

    # RESTRICT (not CASCADE): the monthly cache-retention job deletes
    # artists/albums/tracks with zero interactions. If its "zero
    # interactions" check is ever wrong, RESTRICT makes Postgres refuse
    # the delete with a loud IntegrityError instead of silently
    # cascade-deleting someone's real review/comment/like.
    artist_id: Mapped[int | None] = mapped_column(ForeignKey("artists.id", ondelete="RESTRICT"))
    album_id: Mapped[int | None] = mapped_column(ForeignKey("albums.id", ondelete="RESTRICT"))
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id", ondelete="RESTRICT"))

    parent_interaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE")
    )

    stars: Mapped[int | None] = mapped_column(SmallInteger)
    content: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "("
            "  type = 'review'"
            "  AND num_nonnulls(artist_id, album_id, track_id) = 1"
            "  AND parent_interaction_id IS NULL"
            ") OR ("
            "  type IN ('comment', 'like')"
            "  AND parent_interaction_id IS NOT NULL"
            "  AND artist_id IS NULL AND album_id IS NULL AND track_id IS NULL"
            ")",
            name="interaction_target_shape",
        ),
        CheckConstraint(
            "type != 'review' OR stars IS NOT NULL OR content IS NOT NULL",
            name="interaction_review_has_stars_or_content",
        ),
        CheckConstraint("stars IS NULL OR stars BETWEEN 1 AND 5", name="interaction_stars_range"),
        CheckConstraint("type != 'comment' OR content IS NOT NULL", name="interaction_comment_has_content"),
        CheckConstraint("type != 'like' OR content IS NULL", name="interaction_like_has_no_content"),
        # One review per user per music entity.
        Index(
            "uq_interaction_user_artist_review", "user_id", "artist_id", unique=True,
            postgresql_where="type = 'review' AND artist_id IS NOT NULL",
        ),
        Index(
            "uq_interaction_user_album_review", "user_id", "album_id", unique=True,
            postgresql_where="type = 'review' AND album_id IS NOT NULL",
        ),
        Index(
            "uq_interaction_user_track_review", "user_id", "track_id", unique=True,
            postgresql_where="type = 'review' AND track_id IS NOT NULL",
        ),
        # One like per user per target (review or comment).
        Index(
            "uq_interaction_user_like_parent", "user_id", "parent_interaction_id", unique=True,
            postgresql_where="type = 'like'",
        ),
        # Fast lookup of a review's replies (comments + likes).
        Index("ix_interaction_parent", "parent_interaction_id"),
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    parent: Mapped["Interaction | None"] = relationship(remote_side=[id])
