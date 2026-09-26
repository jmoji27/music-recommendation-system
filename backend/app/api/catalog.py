"""Public catalog browsing — search and album lookup. No login required:
these use Spotify's Client Credentials flow (app-level, not user-scoped),
since search results and album metadata aren't personal data.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.ratelimit import catalog_limit
from app.services.spotify_sync import get_album_with_tracks, search_albums, search_tracks

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/albums/search", dependencies=[Depends(catalog_limit)])
async def search(q: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await search_albums(db, q)


@router.get("/albums/{spotify_album_id}", dependencies=[Depends(catalog_limit)])
async def album_detail(spotify_album_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return await get_album_with_tracks(db, spotify_album_id)


@router.get("/tracks/search", dependencies=[Depends(catalog_limit)])
async def search_track_catalog(q: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await search_tracks(db, q)
