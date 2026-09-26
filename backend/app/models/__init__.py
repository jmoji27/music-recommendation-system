"""Import every model module so Base.metadata is fully populated for
Alembic autogenerate and for anything that calls Base.metadata.create_all.
"""

from app.models.conversation import Conversation, Message
from app.models.follow import Follow
from app.models.interaction import Interaction, InteractionType
from app.models.listening_snapshot import ListeningSnapshot
from app.models.spotify_entities import Album, Artist, Track
from app.models.user import User

__all__ = [
    "Conversation",
    "Message",
    "Follow",
    "Interaction",
    "InteractionType",
    "ListeningSnapshot",
    "Album",
    "Artist",
    "Track",
    "User",
]
