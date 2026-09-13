from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.services.spotify_sync import (
    get_now_playing,
    get_top_albums_for_user,
    get_top_artists_for_user,
    get_top_tracks_for_user,
)

router = APIRouter(tags=["playback"])


@router.get("/me/now-playing")
async def now_playing(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict | None:
    return await get_now_playing(db, user)


@router.get("/me/top-tracks")
async def top_tracks(
    time_range: str = "medium_term",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await get_top_tracks_for_user(db, user, time_range=time_range)


@router.get("/me/top-albums")
async def top_albums(
    time_range: str = "medium_term",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await get_top_albums_for_user(db, user, time_range=time_range)


@router.get("/me/top-artists")
async def top_artists(
    time_range: str = "medium_term",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await get_top_artists_for_user(db, user, time_range=time_range)
