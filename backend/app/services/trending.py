"""'Hot right now' — the most-reviewed albums across all of our own
users, for the landing page. Deliberately not a Spotify chart: this is
purely our own interactions table, so it's unrestricted by Spotify's
Development Mode user cap (it never touches a Spotify API call at all).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction, InteractionType
from app.models.spotify_entities import Album, Artist
from app.services.spotify_sync import album_summary


async def get_hot_albums(db: AsyncSession, limit: int = 10) -> list[dict]:
    counts = await db.execute(
        select(Interaction.album_id, func.count().label("review_count"))
        .where(Interaction.type == InteractionType.REVIEW, Interaction.album_id.is_not(None))
        .group_by(Interaction.album_id)
        .order_by(func.count().desc())
        .limit(limit)
    )

    results = []
    for album_id, review_count in counts:
        album = await db.get(Album, album_id)
        artist = await db.get(Artist, album.artist_id)
        summary = album_summary(album, artist)
        summary["review_count"] = review_count
        results.append(summary)
    return results
