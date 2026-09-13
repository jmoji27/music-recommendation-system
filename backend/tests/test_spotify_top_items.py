"""Verifies /me/top-tracks and /me/top-artists against the real schema,
with Spotify mocked (respx). These power the "interactive cards instead
of an empty search box" card UI shown right after login.
"""

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from app.models.spotify_entities import Album, Artist, Track


async def _log_in(client) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fake-access-token",
                    "refresh_token": "fake-refresh-token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        )
        mock.get("https://api.spotify.com/v1/me").mock(
            return_value=Response(
                200,
                json={"id": "spotify_test_user_2", "display_name": "Test User", "email": "t2@example.com", "images": []},
            )
        )

        login_response = await client.get("/auth/spotify/login", follow_redirects=False)
        state = login_response.cookies["oauth_state"]
        callback_response = await client.get(
            "/auth/spotify/callback", params={"code": "fake-code", "state": state}
        )
        assert callback_response.status_code == 200


@pytest.mark.asyncio
async def test_top_tracks_caches_and_returns_cards(client, db_session):
    await _log_in(client)

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://api.spotify.com/v1/me/top/tracks").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "top_track_1",
                            "name": "Top Track One",
                            "duration_ms": 210000,
                            "artists": [{"id": "top_artist_1", "name": "Top Artist"}],
                            "album": {
                                "id": "top_album_1",
                                "name": "Top Album",
                                "release_date": "2021-01-01",
                                "images": [{"url": "http://example.com/top-album.jpg"}],
                            },
                        }
                    ]
                },
            )
        )

        response = await client.get("/me/top-tracks")
        assert response.status_code == 200
        body = response.json()

    assert len(body) == 1
    assert body[0]["name"] == "Top Track One"
    assert body[0]["album"]["name"] == "Top Album"
    assert body[0]["artist"]["name"] == "Top Artist"

    track = await db_session.scalar(select(Track).where(Track.spotify_id == "top_track_1"))
    album = await db_session.scalar(select(Album).where(Album.spotify_id == "top_album_1"))
    assert track is not None and album is not None
    assert track.album_id == album.id


@pytest.mark.asyncio
async def test_top_artists_caches_full_genre_and_image_data(client, db_session):
    await _log_in(client)

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://api.spotify.com/v1/me/top/artists").mock(
            return_value=Response(
                200,
                json={
                    "items": [
                        {
                            "id": "top_artist_2",
                            "name": "Full Data Artist",
                            "genres": ["synthpop", "art rock"],
                            "images": [{"url": "http://example.com/artist.jpg"}],
                        }
                    ]
                },
            )
        )

        response = await client.get("/me/top-artists")
        assert response.status_code == 200
        body = response.json()

    assert body[0]["name"] == "Full Data Artist"
    assert body[0]["genres"] == ["synthpop", "art rock"]
    assert body[0]["image_url"] == "http://example.com/artist.jpg"

    artist = await db_session.scalar(select(Artist).where(Artist.spotify_id == "top_artist_2"))
    assert artist is not None
    assert artist.genres == ["synthpop", "art rock"]
    assert artist.image_url == "http://example.com/artist.jpg"


@pytest.mark.asyncio
async def test_top_tracks_requires_auth(client):
    response = await client.get("/me/top-tracks")
    assert response.status_code == 401
