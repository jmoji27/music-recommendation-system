"""One-shot LLM output (no chat) turning a genre breakdown + top artists
into a short taste summary and adjacent recommendations. Gracefully
degrades to "not available" when no GEMINI_API_KEY is configured,
rather than erroring — this is meant to be optional, not a hard
dependency for the rest of the app.
"""

from google import genai
from pydantic import BaseModel

from app.config import settings

_MODEL = "gemini-3.8-flash"


class TasteRecommendation(BaseModel):
    summary: str
    recommended_genres: list[str]
    recommended_artists: list[str]


async def generate_taste_recommendation(genre_counts: dict[str, int], top_artist_names: list[str]) -> dict:
    if not settings.gemini_api_key:
        return {"available": False}

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = (
        "You are a music taste analyst. A listener's most common genres among "
        f"their top artists, with counts, are: {genre_counts}. Their top artists "
        f"include: {', '.join(top_artist_names)}.\n\n"
        "Write a short, specific 2-3 sentence summary of what this says about "
        "their taste — reference actual genres/artists, not generic filler. "
        "Then suggest 3 genres and 3 specific artists they likely haven't fully "
        "explored yet but would probably enjoy, based on adjacency to their "
        "existing taste (not just more of the same)."
    )

    interaction = await client.aio.interactions.create(
        model=_MODEL,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": TasteRecommendation.model_json_schema(),
        },
    )
    result = TasteRecommendation.model_validate_json(interaction.output_text)
    return {"available": True, **result.model_dump()}
