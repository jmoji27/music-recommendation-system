from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.auth_google import router as auth_google_router
from app.api.catalog import router as catalog_router
from app.api.interactions import router as interactions_router
from app.api.playback import router as playback_router
from app.api.trending import router as trending_router
from app.api.users import router as users_router
from app.config import settings
from app.services.token_service import SpotifyNotConnected

app = FastAPI(title="Music Recommendation System", version="0.1.0")


@app.exception_handler(SpotifyNotConnected)
async def spotify_not_connected_handler(request: Request, exc: SpotifyNotConnected) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "Connect your Spotify account to see this — accounts created with Google don't have Spotify data."},
    )

# allow_credentials=True is required for the session cookie to be sent
# on cross-origin requests from the frontend dev server; that requires
# an explicit origin below rather than "*" (browsers refuse to combine
# a wildcard origin with credentialed requests).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(auth_google_router)
app.include_router(catalog_router)
app.include_router(interactions_router)
app.include_router(playback_router)
app.include_router(trending_router)
app.include_router(users_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
