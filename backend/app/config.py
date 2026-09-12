from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment / .env.

    Secrets (Spotify client secret, LLM API key, JWT secret) must only ever
    live here on the backend — never shipped to the frontend bundle.
    """

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/music_rec"

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8000/auth/spotify/callback"

    gemini_api_key: str = ""

    # Fernet key (Fernet.generate_key()) used to encrypt Spotify tokens at
    # rest before writing them to the users table.
    token_encryption_key: str = ""

    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
