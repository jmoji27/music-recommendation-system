from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.playback import router as playback_router

app = FastAPI(title="Music Recommendation System", version="0.1.0")

app.include_router(auth_router)
app.include_router(playback_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
