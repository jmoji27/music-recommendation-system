from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.ratelimit import gemini_limit
from app.models.user import User
from app.services.recommendations import generate_taste_recommendation
from app.services.taste import get_taste_summary

router = APIRouter(tags=["taste"])


@router.get("/me/taste-summary", dependencies=[Depends(gemini_limit)])
async def taste_summary(
    time_range: str = "medium_term",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_taste_summary(db, user, time_range=time_range)


@router.get("/me/recommendations", dependencies=[Depends(gemini_limit)])
async def recommendations(
    time_range: str = "medium_term",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    summary = await get_taste_summary(db, user, time_range=time_range)
    return await generate_taste_recommendation(summary["genre_counts"], summary["top_artist_names"])
