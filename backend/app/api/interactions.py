from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.interaction import InteractionType
from app.models.user import User
from app.services import interactions as interactions_service

router = APIRouter(tags=["interactions"])


class ReviewCreate(BaseModel):
    stars: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_stars_or_content(self) -> "ReviewCreate":
        if self.stars is None and self.content is None:
            raise ValueError("Provide stars, content, or both.")
        return self


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)


@router.post("/albums/{spotify_album_id}/reviews", status_code=status.HTTP_201_CREATED)
async def create_album_review(
    spotify_album_id: str,
    body: ReviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await interactions_service.create_album_review(db, user, spotify_album_id, body.stars, body.content)
    except interactions_service.AlreadyReviewed:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already reviewed this album.")


@router.get("/albums/{spotify_album_id}/reviews")
async def list_album_reviews(spotify_album_id: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await interactions_service.list_album_reviews(db, spotify_album_id)


@router.post("/reviews/{review_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    review_id: int,
    body: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await interactions_service.create_comment(db, user, review_id, body.content)
    except interactions_service.TargetNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found.")


@router.post("/reviews/{review_id}/like", status_code=status.HTTP_201_CREATED)
async def like_review(
    review_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await interactions_service.like_interaction(db, user, review_id, InteractionType.REVIEW)
    except interactions_service.TargetNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found.")
    except interactions_service.AlreadyLiked:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already liked this.")


@router.post("/comments/{comment_id}/like", status_code=status.HTTP_201_CREATED)
async def like_comment(
    comment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await interactions_service.like_interaction(db, user, comment_id, InteractionType.COMMENT)
    except interactions_service.TargetNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found.")
    except interactions_service.AlreadyLiked:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already liked this.")
