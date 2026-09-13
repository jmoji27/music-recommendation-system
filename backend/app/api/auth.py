from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security import create_oauth_state, create_session_token, encrypt_token, verify_oauth_state
from app.services import spotify

router = APIRouter(prefix="/auth/spotify", tags=["auth"])

_OAUTH_STATE_COOKIE = "oauth_state"
_SESSION_COOKIE = "session"


@router.get("/login")
async def login() -> RedirectResponse:
    state = create_oauth_state()
    response = RedirectResponse(spotify.build_authorize_url(state))
    # Double-submit cookie pattern: the callback checks this cookie
    # against the `state` query param Spotify sends back, so a
    # cross-site request forging the callback can't succeed without
    # also having set this cookie in the victim's browser.
    # Must match create_oauth_state()'s expiry (30 min) — if the cookie
    # died first, the callback would 400 even with a still-valid token.
    response.set_cookie(
        _OAUTH_STATE_COOKIE, state, httponly=True, samesite="lax", max_age=1800
    )
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

    token_data = await spotify.exchange_code_for_tokens(code)
    profile = await spotify.get_current_user_profile(token_data["access_token"])

    user = await db.scalar(select(User).where(User.spotify_id == profile["id"]))
    if user is None:
        user = User(
            spotify_id=profile["id"],
            display_name=profile.get("display_name") or profile["id"],
            email=profile.get("email"),
            avatar_url=(profile.get("images") or [{}])[0].get("url"),
        )
        db.add(user)
    else:
        user.display_name = profile.get("display_name") or user.display_name
        user.email = profile.get("email")
        user.avatar_url = (profile.get("images") or [{}])[0].get("url")

    user.spotify_access_token_encrypted = encrypt_token(token_data["access_token"])
    user.spotify_refresh_token_encrypted = encrypt_token(token_data["refresh_token"])
    user.spotify_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    await db.commit()
    await db.refresh(user)

    session_token = create_session_token(user.id)
    # No frontend to redirect into yet — plain confirmation response for now.
    response = Response(status_code=status.HTTP_200_OK, content="Logged in.")
    response.delete_cookie(_OAUTH_STATE_COOKIE)
    response.set_cookie(_SESSION_COOKIE, session_token, httponly=True, samesite="lax")
    return response


@router.post("/logout")
async def logout() -> Response:
    # Our session is a stateless, signed JWT — there's no server-side
    # session record to revoke. "Logout" just tells the browser to
    # forget the cookie; the token itself would still verify as valid
    # if somehow replayed, until it naturally expires
    # (access_token_expire_minutes, currently 60 min). That's an
    # accepted trade-off for a token this short-lived, not an oversight —
    # a real revocation list would need server-side state we don't have.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(_SESSION_COOKIE)
    return response
