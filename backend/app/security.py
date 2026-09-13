"""Encryption for stored Spotify tokens + our own session JWTs.

Spotify tokens are encrypted (not hashed — we need the plaintext back to
call Spotify's API) with Fernet before being written to the users table.
Our session token is a separate, short-lived JWT unrelated to Spotify's
tokens, so a leaked session cookie doesn't expose Spotify credentials.
"""

from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import settings


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set — generate one and add it to .env")
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def create_session_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> int:
    """Returns the user id encoded in the token, or raises JWTError."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return int(payload["sub"])


def create_oauth_state() -> str:
    """A short-lived, signed CSRF token for the Spotify OAuth `state`
    parameter. Signed rather than looked up server-side, so it works
    without shared memory across restarts/multiple workers.

    30 minutes, not something tighter: with show_dialog=true forcing a
    real interactive consent screen (rather than an instant silent
    redirect when Spotify already has a session), a first-time user has
    to actually log into Spotify and read the permissions — 10 minutes
    was too easy to blow past. This window only bounds a CSRF token, not
    a credential, so a longer value doesn't weaken anything.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    return jwt.encode({"purpose": "oauth_state", "exp": expires_at}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_oauth_state(state: str) -> bool:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return False
    return payload.get("purpose") == "oauth_state"


__all__ = [
    "encrypt_token",
    "decrypt_token",
    "create_session_token",
    "decode_session_token",
    "create_oauth_state",
    "verify_oauth_state",
    "JWTError",
]
