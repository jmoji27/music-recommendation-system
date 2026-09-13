"""Periodic capture of a user's Spotify 'top items' for a given time range,
so we can chart taste over time rather than only showing the current
snapshot. Populated by the spotify_sync background job.
"""

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class TimeRange(str, enum.Enum):
    SHORT_TERM = "short_term"  # ~last 4 weeks, per Spotify's API
    MEDIUM_TERM = "medium_term"  # ~last 6 months
    LONG_TERM = "long_term"  # several years


class ListeningSnapshot(Base):
    __tablename__ = "listening_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # values_callable: without it, SQLAlchemy persists the enum member's
    # *name* ("SHORT_TERM") instead of its *value* ("short_term"), which
    # doesn't match the lowercase values the Postgres enum type actually
    # has — see the identical issue on Interaction.type.
    time_range: Mapped[TimeRange] = mapped_column(
        Enum(TimeRange, name="time_range", values_callable=lambda enum_cls: [member.value for member in enum_cls])
    )

    # Denormalized on purpose: this is a point-in-time snapshot for charting
    # history, not a live-queryable relation — so we store the ranked
    # Spotify IDs and computed genre counts directly rather than joining
    # through artists/tracks (which may since change or be re-cached).
    top_artist_spotify_ids: Mapped[list[str]] = mapped_column(JSON)
    top_track_spotify_ids: Mapped[list[str]] = mapped_column(JSON)
    genre_counts: Mapped[dict[str, int]] = mapped_column(JSON)

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()
