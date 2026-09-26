from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cookies import cookie_kwargs
from app.db import get_db
from app.models.user import User
from app.security import JWTError, create_session_token, decode_session_token, should_renew


async def get_current_user(
    response: Response,
    session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        claims = decode_session_token(session)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    user = await db.get(User, claims["user_id"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    if should_renew(claims):
        response.set_cookie(
            "session",
            create_session_token(user.id, auth_at=claims["auth_at_dt"]),
            httponly=True,
            **cookie_kwargs(),
        )
    return user


async def get_optional_user(
    session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user, but anonymous (or a bad/expired session)
    just yields None — for public pages that show a bit more to logged-in
    viewers, like "are you following this person"."""
    if session is None:
        return None
    try:
        claims = decode_session_token(session)
    except JWTError:
        return None
    return await db.get(User, claims["user_id"])
