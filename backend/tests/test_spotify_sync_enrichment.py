"""Regression test for a real bug found via a live browser check: an
artist first cached from a partial stub (id/name only — what
now-playing/top-tracks/album tracklists give) stayed permanently
missing its image/genres even after a richer source (top-artists) saw
the same artist, because _get_or_create_artist only set those fields on
creation. Every "Your top artists" card showed a blank placeholder image.
"""

import pytest
from sqlalchemy import select

from app.models.spotify_entities import Artist
from app.services.spotify_sync import _get_or_create_artist


@pytest.mark.asyncio
async def test_partial_stub_gets_enriched_by_later_full_data(db_session):
    partial = {"id": "artist_enrich_1", "name": "Some Artist"}
    stub = await _get_or_create_artist(db_session, partial)
    await db_session.commit()
    assert stub.genres == []
    assert stub.image_url is None

    full = {
        "id": "artist_enrich_1",
        "name": "Some Artist",
        "genres": ["hyperpop", "art pop"],
        "images": [{"url": "http://example.com/artist.jpg"}],
    }
    enriched = await _get_or_create_artist(db_session, full)
    await db_session.commit()

    assert enriched.id == stub.id  # same row, not a duplicate
    assert enriched.genres == ["hyperpop", "art pop"]
    assert enriched.image_url == "http://example.com/artist.jpg"

    reloaded = await db_session.scalar(select(Artist).where(Artist.spotify_id == "artist_enrich_1"))
    assert reloaded.genres == ["hyperpop", "art pop"]


@pytest.mark.asyncio
async def test_richer_data_never_overwritten_by_a_later_partial_stub(db_session):
    full = {
        "id": "artist_enrich_2",
        "name": "Full Artist",
        "genres": ["indie rock"],
        "images": [{"url": "http://example.com/full.jpg"}],
    }
    await _get_or_create_artist(db_session, full)
    await db_session.commit()

    partial = {"id": "artist_enrich_2", "name": "Full Artist"}
    result = await _get_or_create_artist(db_session, partial)
    await db_session.commit()

    assert result.genres == ["indie rock"]
    assert result.image_url == "http://example.com/full.jpg"
