from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.auth_google import router as auth_google_router
from app.api.catalog import router as catalog_router
from app.api.interactions import router as interactions_router
from app.api.messaging import router as messaging_router
from app.api.playback import router as playback_router
from app.api.providers import router as providers_router
from app.api.social import router as social_router
from app.api.taste import router as taste_router
from app.api.trending import router as trending_router
from app.api.users import router as users_router
from app.config import settings
from app.ratelimit import baseline_reads, baseline_writes
from app.services.blocks import BlockedByThem, BlockedByYou
from app.services.token_service import SpotifyNotConnected

# Interactive docs/OpenAPI describe every endpoint to anyone who finds them;
# useful locally, unnecessary attack-surface documentation in production.
_docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="Music Recommendation System",
    version="0.1.0",
    dependencies=[Depends(baseline_reads), Depends(baseline_writes)],
    **_docs,
)


@app.exception_handler(SpotifyNotConnected)
async def spotify_not_connected_handler(request: Request, exc: SpotifyNotConnected) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "Connect your Spotify account to see this — accounts created with Google don't have Spotify data."},
    )

@app.exception_handler(BlockedByYou)
async def blocked_by_you_handler(request: Request, exc: BlockedByYou) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": "You've blocked this person. Unblock them first."})


@app.exception_handler(BlockedByThem)
async def blocked_by_them_handler(request: Request, exc: BlockedByThem) -> JSONResponse:
    # Same shape as a missing resource, so a block isn't revealed to the blocked person.
    return JSONResponse(status_code=404, content={"detail": "Not found."})


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def require_custom_header_in_production(request: Request, call_next):
    """CSRF defense for production. There the session cookie is
    SameSite=None (frontend and backend are on different sites), so a
    hostile page could make a logged-in visitor's browser send body-less
    POSTs (follow, like...) that skip CORS preflight as "simple"
    requests. Requiring a custom header on unsafe methods forces a
    preflight, which our CORS allow-list rejects for any other origin.
    Off in development so /docs "Try it out" and curl keep working.
    """
    if (
        settings.is_production
        and request.method in _UNSAFE_METHODS
        and request.headers.get("x-requested-with") != "fetch"
    ):
        return JSONResponse(status_code=403, content={"detail": "Missing X-Requested-With header."})
    return await call_next(request)


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
app.include_router(providers_router)
app.include_router(catalog_router)
app.include_router(interactions_router)
app.include_router(messaging_router)
app.include_router(playback_router)
app.include_router(social_router)
app.include_router(taste_router)
app.include_router(trending_router)
app.include_router(users_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
