"""Turns Spotify API JSON into local cache rows (artists/albums/tracks),
upserting on spotify_id per the lazy-fetch-on-lookup design: nothing is
pre-populated, a row only exists here once something references it.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spotify_entities import Album, Artist, Track
from app.models.user import User
from app.services import spotify
from app.services.token_service import get_valid_access_token


def _first_image_url(images: list[dict] | None) -> str | None:
    return images[0]["url"] if images else None


async def _get_or_create_artist(db: AsyncSession, artist_data: dict) -> Artist:
    existing = await db.scalar(select(Artist).where(Artist.spotify_id == artist_data["id"]))
    if existing is not None:
        return existing

    # The currently-playing endpoint only gives id/name for artists, not
    # genres or images — those require a separate GET /artists/{id} call,
    # which the artist-detail page (not built yet) can make and enrich
    # this same cached row later.
    artist = Artist(spotify_id=artist_data["id"], name=artist_data["name"], genres=[])
    db.add(artist)
    await db.flush()
    return artist


async def _get_or_create_album(db: AsyncSession, album_data: dict, artist: Artist) -> Album:
    existing = await db.scalar(select(Album).where(Album.spotify_id == album_data["id"]))
    if existing is not None:
        return existing

    album = Album(
        spotify_id=album_data["id"],
        name=album_data["name"],
        artist_id=artist.id,
        release_date=album_data.get("release_date"),
        image_url=_first_image_url(album_data.get("images")),
    )
    db.add(album)
    await db.flush()
    return album


async def _get_or_create_track(db: AsyncSession, track_data: dict, artist: Artist, album: Album) -> Track:
    existing = await db.scalar(select(Track).where(Track.spotify_id == track_data["id"]))
    if existing is not None:
        return existing

    track = Track(
        spotify_id=track_data["id"],
        name=track_data["name"],
        artist_id=artist.id,
        album_id=album.id,
        duration_ms=track_data.get("duration_ms"),
    )
    db.add(track)
    await db.flush()
    return track


async def get_now_playing(db: AsyncSession, user: User) -> dict | None:
    """Fetches the user's currently playing track from Spotify, caching
    the artist/album/track locally, and returns a plain dict for the API
    response. None if nothing is currently playing.
    """
    access_token = await get_valid_access_token(db, user)
    data = await spotify.get_currently_playing(access_token)
    if data is None or data.get("item") is None:
        return None

    item = data["item"]
    primary_artist_data = item["artists"][0]

    artist = await _get_or_create_artist(db, primary_artist_data)
    album = await _get_or_create_album(db, item["album"], artist)
    track = await _get_or_create_track(db, item, artist, album)

    # Build the response from already-loaded attributes BEFORE commit —
    # commit() expires them by default (expire_on_commit=True), and
    # touching an expired attribute afterwards tries a synchronous
    # reload that async SQLAlchemy can't do outside an awaited call
    # (raises MissingGreenlet).
    result = {
        "is_playing": data.get("is_playing", False),
        "progress_ms": data.get("progress_ms"),
        "track": {"id": track.id, "spotify_id": track.spotify_id, "name": track.name, "duration_ms": track.duration_ms},
        "album": {
            "id": album.id,
            "spotify_id": album.spotify_id,
            "name": album.name,
            "image_url": album.image_url,
        },
        "artist": {"id": artist.id, "spotify_id": artist.spotify_id, "name": artist.name},
    }
    await db.commit()
    return result
