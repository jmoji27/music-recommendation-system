from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.services.spotify_sync import get_now_playing

router = APIRouter(tags=["playback"])


@router.get("/me/now-playing")
async def now_playing(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict | None:
    return await get_now_playing(db, user)
