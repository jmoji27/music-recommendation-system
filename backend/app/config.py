import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS = {"change-me-in-.env", "change-me-generate-a-random-value", ""}
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment / .env.

    Secrets (Spotify client secret, LLM API key, JWT secret) must only ever
    live here on the backend — never shipped to the frontend bundle.
    """

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/music_rec"

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    # Spotify requires an explicit loopback IP literal for local dev —
    # "localhost" is rejected outright, only 127.0.0.1 / [::1] are allowed.
    spotify_redirect_uri: str = "http://127.0.0.1:8000/auth/spotify/callback"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/auth/google/callback"

    gemini_api_key: str = ""

    # Fernet key (Fernet.generate_key()) used to encrypt Spotify tokens at
    # rest before writing them to the users table.
    token_encryption_key: str = ""

    # The React dev server's origin — needed for CORS since it's a
    # different port than the backend (127.0.0.1:5173 vs :8000), which
    # makes it cross-origin even though it's same-site.
    frontend_origin: str = "http://127.0.0.1:5173"

    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Sessions renew themselves while you're active (see api/deps.py), but
    # never past this many days after the original login.
    session_max_age_days: int = 30

    # On by default; only tests/benchmarks should turn it off.
    rate_limit_enabled: bool = True

    # "development" (default, matches local http://127.0.0.1) or
    # "production" — controls cookie Secure/SameSite flags (see
    # app/cookies.py). Set ENVIRONMENT=production on the real deployment.
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        """A placeholder or short JWT secret lets anyone who knows it forge
        a login as any user. Refuse to boot in production with one; in
        development just warn loudly."""
        weak = self.jwt_secret in _PLACEHOLDER_SECRETS or len(self.jwt_secret) < _MIN_SECRET_LENGTH
        if not weak:
            return self
        message = (
            "JWT_SECRET is a placeholder or shorter than 32 characters — anyone could forge session cookies. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
        if self.environment == "production":
            raise ValueError(message)
        logger.warning(message)
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
