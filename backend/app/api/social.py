"""Profiles, follows, avatars and the friends feed."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db import get_db
from app.ratelimit import avatar_limit, follow_limit
from app.models.user import User
from app.services import profiles

router = APIRouter(tags=["social"])


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)


@router.patch("/me")
async def update_me(
    body: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        await profiles.update_display_name(db, user, body.display_name)
    except profiles.InvalidDisplayName:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Display name must be 1-{profiles.MAX_DISPLAY_NAME} characters.",
        )
    return await profiles.get_profile(db, user.id, user)


@router.put("/me/avatar", dependencies=[Depends(avatar_limit)])
async def upload_avatar(
    request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """The raw image bytes are the request body (no multipart). Streamed
    with a hard cap so an oversized upload is rejected without buffering
    all of it."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > profiles.MAX_AVATAR_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image too large (max 200KB).")

    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > profiles.MAX_AVATAR_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image too large (max 200KB).")

    try:
        await profiles.set_avatar(db, user, bytes(data))
    except profiles.InvalidImage:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Upload a PNG, JPEG or WebP image.")
    return await profiles.get_profile(db, user.id, user)


@router.delete("/me/avatar")
async def remove_avatar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await profiles.clear_avatar(db, user)
    return await profiles.get_profile(db, user.id, user)


@router.get("/me/friends/feed")
async def friends_feed(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await profiles.get_friends_feed(db, user)


# Declared before /users/{user_id} so "search" isn't parsed as a user id.
@router.get("/users/search")
async def search_users(q: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await profiles.search_users(db, q, user)


@router.get("/users/{user_id}")
async def get_user_profile(
    user_id: int, viewer: User | None = Depends(get_optional_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await profiles.get_profile(db, user_id, viewer)
    except profiles.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")


@router.get("/users/{user_id}/avatar")
async def get_user_avatar(user_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    avatar = await profiles.get_avatar(db, user_id)
    if avatar is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No custom avatar.")
    data, content_type = avatar
    return Response(
        content=data,
        media_type=content_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=60"},
    )


@router.get("/users/{user_id}/activity")
async def get_user_activity(user_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await profiles.get_user_activity(db, user_id)
    except profiles.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")


@router.get("/users/{user_id}/followers")
async def get_followers(user_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    try:
        return await profiles.list_followers(db, user_id)
    except profiles.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")


@router.get("/users/{user_id}/following")
async def get_following(user_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    try:
        return await profiles.list_following(db, user_id)
    except profiles.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")


@router.post("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(follow_limit)])
async def follow_user(
    user_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    try:
        await profiles.follow(db, user, user_id)
    except profiles.CannotFollowSelf:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't follow yourself.")
    except profiles.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    user_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    await profiles.unfollow(db, user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
