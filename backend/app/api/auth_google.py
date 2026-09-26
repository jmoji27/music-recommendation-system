from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import logging

import httpx

from app.api.login_errors import EXPIRED, FAILED, NOT_CONFIGURED, login_error_redirect
from app.config import settings
from app.cookies import cookie_kwargs
from app.db import get_db
from app.ratelimit import auth_limit
from app.models.user import User
from app.security import create_oauth_state, create_session_token, verify_oauth_state
from app.services import google

router = APIRouter(prefix="/auth/google", tags=["auth"])

logger = logging.getLogger(__name__)

_OAUTH_STATE_COOKIE = "oauth_state"
_SESSION_COOKIE = "session"


@router.get("/login", dependencies=[Depends(auth_limit)])
async def login() -> RedirectResponse:
    if not (settings.google_client_id and settings.google_client_secret):
        return login_error_redirect("google", NOT_CONFIGURED)
    state = create_oauth_state()
    response = RedirectResponse(google.build_authorize_url(state))
    response.set_cookie(_OAUTH_STATE_COOKIE, state, httponly=True, max_age=1800, **cookie_kwargs())
    return response


@router.get("/callback", dependencies=[Depends(auth_limit)])
async def callback(
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None, alias=_OAUTH_STATE_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if oauth_state is None or oauth_state != state or not verify_oauth_state(state):
        return login_error_redirect("google", EXPIRED)

    try:
        token_data = await google.exchange_code_for_tokens(code)
        profile = await google.get_user_info(token_data["access_token"])
    except httpx.HTTPError:
        logger.warning("Google login failed", exc_info=True)
        return login_error_redirect("google", FAILED)

    user = await db.scalar(select(User).where(User.google_id == profile["sub"]))
    if user is None:
        # A Google sign-in with the same email as an existing
        # Spotify-only account links onto it, rather than creating a
        # second, disconnected account — so someone who first tried
        # the app via Google (or vice versa) doesn't end up split
        # across two accounts if their emails happen to match.
        user = await db.scalar(select(User).where(User.email == profile.get("email")))
        if user is not None:
            user.google_id = profile["sub"]
        else:
            user = User(
                google_id=profile["sub"],
                display_name=profile.get("name") or profile["email"],
                email=profile.get("email"),
                avatar_url=profile.get("picture"),
            )
            db.add(user)
    else:
        user.display_name = profile.get("name") or user.display_name
        user.avatar_url = profile.get("picture") or user.avatar_url

    await db.commit()
    await db.refresh(user)

    session_token = create_session_token(user.id)
    response = RedirectResponse(url=settings.frontend_origin, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(_OAUTH_STATE_COOKIE, **cookie_kwargs())
    response.set_cookie(_SESSION_COOKIE, session_token, httponly=True, **cookie_kwargs())
    return response
