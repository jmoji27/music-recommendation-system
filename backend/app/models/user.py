from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Spotify is the only login method, so this is required and unique.
    spotify_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    # Spotify OAuth tokens — encrypted at rest at the application layer
    # before being written here (never store plaintext refresh tokens).
    spotify_access_token_encrypted: Mapped[str | None] = mapped_column(String(2048))
    spotify_refresh_token_encrypted: Mapped[str | None] = mapped_column(String(2048))
    spotify_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
