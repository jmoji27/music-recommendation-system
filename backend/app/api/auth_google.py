from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cookies import cookie_kwargs
from app.db import get_db
from app.models.user import User
from app.security import create_oauth_state, create_session_token, verify_oauth_state
from app.services import google

router = APIRouter(prefix="/auth/google", tags=["auth"])

_OAUTH_STATE_COOKIE = "oauth_state"
_SESSION_COOKIE = "session"


@router.get("/login")
async def login() -> RedirectResponse:
    state = create_oauth_state()
    response = RedirectResponse(google.build_authorize_url(state))
    response.set_cookie(_OAUTH_STATE_COOKIE, state, httponly=True, max_age=1800, **cookie_kwargs())
    return response


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None, alias=_OAUTH_STATE_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if oauth_state is None or oauth_state != state or not verify_oauth_state(state):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired OAuth state")

    token_data = await google.exchange_code_for_tokens(code)
    profile = await google.get_user_info(token_data["access_token"])

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
    response = Response(status_code=status.HTTP_200_OK, content="Logged in.")
    response.delete_cookie(_OAUTH_STATE_COOKIE, **cookie_kwargs())
    response.set_cookie(_SESSION_COOKIE, session_token, httponly=True, **cookie_kwargs())
    return response
