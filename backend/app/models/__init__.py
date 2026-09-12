"""Import every model module so Base.metadata is fully populated for
Alembic autogenerate and for anything that calls Base.metadata.create_all.
"""

from app.models.comment import Comment
from app.models.follow import Follow
from app.models.like import Like
from app.models.listening_snapshot import ListeningSnapshot
from app.models.review import Review
from app.models.spotify_entities import Album, Artist, Track
from app.models.user import User

__all__ = [
    "Comment",
    "Follow",
    "Like",
    "ListeningSnapshot",
    "Review",
    "Album",
    "Artist",
    "Track",
    "User",
]
