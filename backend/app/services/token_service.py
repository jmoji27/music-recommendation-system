from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security import decrypt_token, encrypt_token
from app.services import spotify

# Refresh a little early so a request doesn't fail mid-flight on an
# access token that expires in the next few seconds.
_EXPIRY_SAFETY_MARGIN = timedelta(seconds=30)


async def get_valid_access_token(db: AsyncSession, user: User) -> str:
    now = datetime.now(timezone.utc)
    if user.spotify_token_expires_at and user.spotify_token_expires_at - _EXPIRY_SAFETY_MARGIN > now:
        return decrypt_token(user.spotify_access_token_encrypted)

    refresh_token = decrypt_token(user.spotify_refresh_token_encrypted)
    token_data = await spotify.refresh_access_token(refresh_token)

    user.spotify_access_token_encrypted = encrypt_token(token_data["access_token"])
    user.spotify_token_expires_at = now + timedelta(seconds=token_data["expires_in"])
    # Spotify only sometimes rotates the refresh token on refresh.
    if token_data.get("refresh_token"):
        user.spotify_refresh_token_encrypted = encrypt_token(token_data["refresh_token"])

    await db.commit()
    return decrypt_token(user.spotify_access_token_encrypted)
