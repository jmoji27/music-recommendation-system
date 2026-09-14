"""Public 'hot right now' feed — no login required, since it's just our
own interactions table, not personal Spotify data.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.trending import get_hot_albums

router = APIRouter(tags=["trending"])


@router.get("/hot-albums")
async def hot_albums(limit: int = 10, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await get_hot_albums(db, limit=limit)
