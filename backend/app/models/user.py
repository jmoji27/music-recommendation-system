from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """An account can be identified by Spotify, Google, or (later)
    both — spotify_id/google_id are each nullable, with a CHECK
    ensuring at least one is set. Deliberately not "exactly one": a
    Google-only user should be able to later connect Spotify on the
    same account to unlock personalized recommendations, rather than
    ending up with two separate accounts.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    spotify_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    # A user-uploaded picture overrides avatar_url (the Spotify/Google
    # photo) when present. Stored in Postgres, not on disk, so it survives
    # free-tier hosts with ephemeral filesystems; size-capped at upload.
    # avatar_data is deferred: get_current_user loads a User on every
    # request and shouldn't drag up to 200KB along each time. Only the
    # avatar endpoint loads it (with undefer). avatar_content_type is
    # non-null exactly when avatar_data is, so it doubles as the flag.
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_content_type: Mapped[str | None] = mapped_column(String(64))

    # Spotify OAuth tokens — encrypted at rest at the application layer
    # before being written here (never store plaintext refresh tokens).
    # Only ever populated for users who've connected Spotify.
    spotify_access_token_encrypted: Mapped[str | None] = mapped_column(String(2048))
    spotify_refresh_token_encrypted: Mapped[str | None] = mapped_column(String(2048))
    spotify_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("num_nonnulls(spotify_id, google_id) >= 1", name="user_has_an_identity"),
    )

    @property
    def has_custom_avatar(self) -> bool:
        return self.avatar_content_type is not None

    @property
    def has_spotify(self) -> bool:
        return self.spotify_refresh_token_encrypted is not None
