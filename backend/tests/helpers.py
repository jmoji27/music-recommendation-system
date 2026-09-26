"""Shared helpers for tests that need several users and mocked Spotify
catalog lookups."""

import respx
from httpx import Response
from sqlalchemy import select

from app.models.user import User

ALBUM_X = {
    "id": "album_x",
    "name": "Test Album X",
    "release_date": "2020-01-01",
    "images": [{"url": "http://example.com/x.jpg"}],
    "artists": [{"id": "artist_x", "name": "Artist X"}],
    "tracks": {"items": []},
}

TRACK_ONE = {
    "id": "track_one",
    "name": "Song One",
    "duration_ms": 200000,
    "artists": [{"id": "artist_x", "name": "Artist X"}],
    "album": {"id": "album_x", "name": "Test Album X", "release_date": "2020-01-01", "images": []},
}


def mock_catalog(mock: respx.MockRouter) -> None:
    mock.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(200, json={"access_token": "app-token", "token_type": "Bearer", "expires_in": 3600})
    )
    mock.get("https://api.spotify.com/v1/albums/album_x").mock(return_value=Response(200, json=ALBUM_X))
    mock.get("https://api.spotify.com/v1/tracks/track_one").mock(return_value=Response(200, json=TRACK_ONE))
    mock.get("https://api.spotify.com/v1/search").mock(
        return_value=Response(200, json={"tracks": {"items": [TRACK_ONE]}})
    )


async def user_id(db_session, spotify_id: str) -> int:
    return await db_session.scalar(select(User.id).where(User.spotify_id == spotify_id))


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
