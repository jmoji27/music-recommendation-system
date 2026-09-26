from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["auth"])


@router.get("/auth/providers")
async def providers() -> dict[str, bool]:
    """Which login options this server actually has credentials for, so the
    frontend doesn't offer a button that can only fail."""
    return {
        "spotify": bool(settings.spotify_client_id and settings.spotify_client_secret),
        "google": bool(settings.google_client_id and settings.google_client_secret),
    }
