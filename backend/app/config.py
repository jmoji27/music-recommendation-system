from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # "development" (default, matches local http://127.0.0.1) or
    # "production" — controls cookie Secure/SameSite flags (see
    # app/cookies.py). Set ENVIRONMENT=production on the real deployment.
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
