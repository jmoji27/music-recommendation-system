from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.services import messaging
from app.services.profiles import UserNotFound

router = APIRouter(tags=["messaging"])


class StartConversation(BaseModel):
    to_user_id: int
    track_spotify_id: str = Field(min_length=1, max_length=64)  # required: you start by recommending a song
    body: str | None = Field(default=None, max_length=4000)


class NewMessage(BaseModel):
    body: str | None = Field(default=None, max_length=4000)
    track_spotify_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_something(self) -> "NewMessage":
        if not (self.body and self.body.strip()) and not self.track_spotify_id:
            raise ValueError("Send some text, a song, or both.")
        return self


_ERRORS = {
    messaging.NotFollowing: (status.HTTP_403_FORBIDDEN, "Follow this person before recommending them a song."),
    messaging.CannotMessageSelf: (status.HTTP_400_BAD_REQUEST, "You can't message yourself."),
    messaging.ConversationNotFound: (status.HTTP_404_NOT_FOUND, "Conversation not found."),
    messaging.MessageTooLong: (status.HTTP_422_UNPROCESSABLE_ENTITY, "Message is too long (max 2000 characters)."),
    messaging.EmptyMessage: (status.HTTP_422_UNPROCESSABLE_ENTITY, "Send some text, a song, or both."),
    UserNotFound: (status.HTTP_404_NOT_FOUND, "User not found."),
}


def _http_error(exc: Exception) -> HTTPException:
    code, detail = _ERRORS[type(exc)]
    return HTTPException(code, detail)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def start_conversation(
    body: StartConversation, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await messaging.start_conversation(db, user, body.to_user_id, body.track_spotify_id, body.body)
    except tuple(_ERRORS) as exc:
        raise _http_error(exc)


@router.get("/conversations")
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await messaging.list_conversations(db, user)


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    after_id: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await messaging.get_messages(db, user, conversation_id, after_id)
    except tuple(_ERRORS) as exc:
        raise _http_error(exc)


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: int,
    body: NewMessage,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await messaging.send_message(db, user, conversation_id, body.body, body.track_spotify_id)
    except tuple(_ERRORS) as exc:
        raise _http_error(exc)
