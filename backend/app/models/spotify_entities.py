"""Local cache of Spotify catalog data (artists/albums/tracks).

Keyed by Spotify's own IDs so re-syncing is idempotent (upsert on
spotify_id). We only cache the fields we actually use — this is not meant
to mirror Spotify's full catalog schema.
"""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    image_url: Mapped[str | None] = mapped_column(String(512))
    # When this row was first cached — the retention job's "unused for 6
    # months" check measures from here, not from last access.
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"))
    release_date: Mapped[str | None] = mapped_column(String(10))  # Spotify gives YYYY, YYYY-MM, or YYYY-MM-DD
    image_url: Mapped[str | None] = mapped_column(String(512))
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    artist: Mapped["Artist"] = relationship()


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    spotify_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"))
    album_id: Mapped[int | None] = mapped_column(ForeignKey("albums.id", ondelete="SET NULL"))
    duration_ms: Mapped[int | None]
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    artist: Mapped["Artist"] = relationship()
    album: Mapped["Album | None"] = relationship()
