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
    """Some callers (currently-playing, album tracklists, top-tracks) only
    have a partial artist stub (id/name only) — genres/images are only
    present when the caller already has full artist data (top-artists,
    album/artist detail lookups). If an existing row was cached from a
    partial stub and this call has richer data, enrich it in place
    rather than leaving it permanently incomplete — otherwise an artist
    first seen via a track listing would show a blank image/genre
    forever, even after a richer source became available.
    """
    existing = await db.scalar(select(Artist).where(Artist.spotify_id == artist_data["id"]))
    genres = artist_data.get("genres", [])
    image_url = _first_image_url(artist_data.get("images"))

    if existing is not None:
        if genres and not existing.genres:
            existing.genres = genres
        if image_url and not existing.image_url:
            existing.image_url = image_url
        return existing

    artist = Artist(spotify_id=artist_data["id"], name=artist_data["name"], genres=genres, image_url=image_url)
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


def album_summary(album: Album, artist: Artist) -> dict:
    return {
        "id": album.id,
        "spotify_id": album.spotify_id,
        "name": album.name,
        "release_date": album.release_date,
        "image_url": album.image_url,
        "artist": {"id": artist.id, "spotify_id": artist.spotify_id, "name": artist.name},
    }


def track_summary(track: Track, artist: Artist, album: Album | None) -> dict:
    return {
        "id": track.id,
        "spotify_id": track.spotify_id,
        "name": track.name,
        "duration_ms": track.duration_ms,
        "artist": {"id": artist.id, "name": artist.name},
        "album": (
            {"id": album.id, "spotify_id": album.spotify_id, "name": album.name, "image_url": album.image_url}
            if album is not None
            else None
        ),
    }


async def _cache_full_track(db: AsyncSession, track_data: dict) -> tuple[Track, Artist, Album]:
    artist = await _get_or_create_artist(db, track_data["artists"][0])
    album = await _get_or_create_album(db, track_data["album"], artist)
    track = await _get_or_create_track(db, track_data, artist, album)
    return track, artist, album


async def search_tracks(db: AsyncSession, query: str) -> list[dict]:
    """Public catalog track search (app-level token), caching results —
    used by the "recommend a song" picker."""
    results = await spotify.search_tracks(query)
    summaries = []
    for track_data in results:
        track, artist, album = await _cache_full_track(db, track_data)
        summaries.append(track_summary(track, artist, album))
    await db.commit()
    return summaries


async def ensure_track_cached(db: AsyncSession, spotify_track_id: str) -> Track:
    existing = await db.scalar(select(Track).where(Track.spotify_id == spotify_track_id))
    if existing is not None:
        return existing
    track_data = await spotify.get_track(spotify_track_id)
    track, _, _ = await _cache_full_track(db, track_data)
    await db.commit()
    return track


async def search_albums(db: AsyncSession, query: str) -> list[dict]:
    """Searches Spotify's catalog and caches whatever comes back. Public
    catalog data — no user/session needed, uses the app-level token.
    """
    results = await spotify.search_albums(query)
    # Read attributes into plain dicts before commit — commit() expires
    # loaded attributes by default, and touching one after would try a
    # synchronous reload outside an awaited call (MissingGreenlet).
    summaries = []
    for album_data in results:
        artist = await _get_or_create_artist(db, album_data["artists"][0])
        album = await _get_or_create_album(db, album_data, artist)
        summaries.append(album_summary(album, artist))
    await db.commit()
    return summaries


async def get_album_with_tracks(db: AsyncSession, spotify_album_id: str) -> dict:
    """Fetches one album's full details (including tracklist) and caches
    it, upserting the artist and every track too.
    """
    album_data = await spotify.get_album(spotify_album_id)
    artist = await _get_or_create_artist(db, album_data["artists"][0])
    album = await _get_or_create_album(db, album_data, artist)

    tracks = []
    for track_data in album_data["tracks"]["items"]:
        track_artist_data = track_data["artists"][0]
        track_artist = (
            artist if track_artist_data["id"] == artist.spotify_id else await _get_or_create_artist(db, track_artist_data)
        )
        track = await _get_or_create_track(db, track_data, track_artist, album)
        tracks.append(
            {"id": track.id, "spotify_id": track.spotify_id, "name": track.name, "duration_ms": track.duration_ms}
        )

    result = album_summary(album, artist)
    result["tracks"] = tracks
    await db.commit()
    return result


def _artist_summary(artist: Artist) -> dict:
    return {
        "id": artist.id,
        "spotify_id": artist.spotify_id,
        "name": artist.name,
        "genres": artist.genres,
        "image_url": artist.image_url,
    }


async def get_top_tracks_for_user(db: AsyncSession, user: User, time_range: str = "medium_term") -> list[dict]:
    """The user's own top tracks — used to populate an interactive card
    UI right after login, instead of a global chart Spotify no longer
    exposes to new apps.
    """
    access_token = await get_valid_access_token(db, user)
    items = await spotify.get_top_tracks(access_token, time_range=time_range)

    summaries = []
    for track_data in items:
        artist = await _get_or_create_artist(db, track_data["artists"][0])
        album = await _get_or_create_album(db, track_data["album"], artist)
        track = await _get_or_create_track(db, track_data, artist, album)
        summaries.append(
            {
                "id": track.id,
                "spotify_id": track.spotify_id,
                "name": track.name,
                "duration_ms": track.duration_ms,
                "album": {"id": album.id, "name": album.name, "image_url": album.image_url},
                "artist": {"id": artist.id, "name": artist.name},
            }
        )
    await db.commit()
    return summaries


async def get_top_albums_for_user(db: AsyncSession, user: User, time_range: str = "medium_term") -> list[dict]:
    """Spotify has no direct "top albums" endpoint, so this derives one
    from the user's top tracks — deduped by album, in the order each
    album's first (highest-ranked) track appears. This is what powers
    the album-card UI shown right after login.
    """
    access_token = await get_valid_access_token(db, user)
    # A wider track pull gives better album coverage/variety than just
    # asking for the top ~20, since many will share the same album.
    items = await spotify.get_top_tracks(access_token, time_range=time_range, limit=50)

    seen_spotify_album_ids: set[str] = set()
    summaries = []
    for track_data in items:
        album_data = track_data["album"]
        if album_data["id"] in seen_spotify_album_ids:
            continue
        seen_spotify_album_ids.add(album_data["id"])

        artist = await _get_or_create_artist(db, track_data["artists"][0])
        album = await _get_or_create_album(db, album_data, artist)
        summaries.append(album_summary(album, artist))

    await db.commit()
    return summaries


async def get_top_artists_for_user(db: AsyncSession, user: User, time_range: str = "medium_term") -> list[dict]:
    access_token = await get_valid_access_token(db, user)
    items = await spotify.get_top_artists(access_token, time_range=time_range)

    summaries = []
    for artist_data in items:
        artist = await _get_or_create_artist(db, artist_data)
        summaries.append(_artist_summary(artist))
    await db.commit()
    return summaries


async def ensure_album_cached(db: AsyncSession, spotify_album_id: str) -> Album:
    """Returns the cached Album row for this Spotify id, fetching and
    caching it (with its tracks) first if it isn't cached yet. Used
    when someone reviews an album they haven't already searched/viewed.
    """
    existing = await db.scalar(select(Album).where(Album.spotify_id == spotify_album_id))
    if existing is not None:
        return existing

    await get_album_with_tracks(db, spotify_album_id)
    # get_album_with_tracks returns a plain dict (see the expire_on_commit
    # note above) rather than the ORM row, so re-select it fresh.
    album = await db.scalar(select(Album).where(Album.spotify_id == spotify_album_id))
    assert album is not None
    return album


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
