from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["users"])


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
    }
