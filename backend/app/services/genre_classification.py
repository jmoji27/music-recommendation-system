"""Spotify no longer populates the artist `genres` field at all (verified
live: 0 of 94 real cached artists had any genre tag, including
mainstream ones) — so genre data for the taste pie chart comes from
Gemini classifying artist names using its own music knowledge instead.

Gracefully returns nothing when GEMINI_API_KEY isn't configured, same
pattern as recommendations.py.
"""

from google import genai
from pydantic import BaseModel

from app.config import settings

_MODEL = "gemini-3.8-flash"


class ArtistGenreClassification(BaseModel):
    genres: dict[str, str]  # artist name -> a single primary genre


async def classify_artist_genres(artist_names: list[str]) -> dict[str, str]:
    if not settings.gemini_api_key or not artist_names:
        return {}

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = (
        "For each of these music artists, give their single primary music genre "
        "as a short, common, lowercase genre label (e.g. 'hyperpop', 'indie rock', "
        "'k-pop', 'reggaeton', 'art pop') based on your own knowledge. If you don't "
        "recognize an artist, omit them from the result rather than guessing.\n\n"
        f"Artists: {', '.join(artist_names)}"
    )
    interaction = await client.aio.interactions.create(
        model=_MODEL,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ArtistGenreClassification.model_json_schema(),
        },
    )
    result = ArtistGenreClassification.model_validate_json(interaction.output_text)
    return result.genres
