"""Genre breakdown (for the pie chart) and a recent-listening estimate.

Two honest limitations, worth repeating here since they shape the API
shape:

1. Spotify's public Web API has no "total minutes listened this year"
   endpoint — that's Wrapped-exclusive, computed from data Spotify never
   exposes to third-party apps. "recent_minutes_listened" here is a real
   number, but it's derived from the last ~50 plays (get_recently_played),
   not a year-to-date total.

2. Spotify's artist `genres` field is now empty in practice — verified
   live against their own API (0 of 94 real cached artists had any
   genre tag, including mainstream ones). Genre data instead comes from
   Gemini classifying artist names by its own knowledge
   (genre_classification.py), cached onto the Artist row itself so it's
   a one-time cost per artist, not per request/user.
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spotify_entities import Artist
from app.models.user import User
from app.services import spotify
from app.services.genre_classification import classify_artist_genres
from app.services.spotify_sync import get_top_artists_for_user
from app.services.token_service import get_valid_access_token


async def _ensure_genres_classified(db: AsyncSession, artists: list[dict]) -> None:
    unclassified_names = [artist["name"] for artist in artists if not artist["genres"]]
    if not unclassified_names:
        return

    classifications = await classify_artist_genres(unclassified_names)
    if not classifications:
        return

    for artist in artists:
        genre = classifications.get(artist["name"])
        if not genre:
            continue
        artist["genres"] = [genre]  # reflect in the in-memory summary used below

        artist_row = await db.scalar(select(Artist).where(Artist.spotify_id == artist["spotify_id"]))
        if artist_row is not None and not artist_row.genres:
            artist_row.genres = [genre]

    await db.commit()


async def get_taste_summary(db: AsyncSession, user: User, time_range: str = "medium_term") -> dict:
    artists = await get_top_artists_for_user(db, user, time_range=time_range)
    await _ensure_genres_classified(db, artists)

    genre_counts: Counter = Counter()
    for artist in artists:
        for genre in artist["genres"]:
            genre_counts[genre] += 1

    access_token = await get_valid_access_token(db, user)
    recently_played = await spotify.get_recently_played(access_token, limit=50)
    recent_minutes_listened = round(sum(item["track"]["duration_ms"] for item in recently_played) / 60000)

    top_genres = genre_counts.most_common(8)  # capped for a readable pie chart
    return {
        "genre_counts": dict(top_genres),
        "top_genre": top_genres[0][0] if top_genres else None,
        "recent_minutes_listened": recent_minutes_listened,
        "recent_track_count": len(recently_played),
        "top_artist_names": [artist["name"] for artist in artists[:10]],
    }
