from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageBase(BaseModel):
    author: str
    content: str
    direction: str
    user_id: int


class MessageOut(MessageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    content: str = Field(..., examples=["Bonjour n8n"])
    user_id: int


class HistoryResponse(BaseModel):
    messages: List[MessageOut]


class PendingStatusResponse(BaseModel):
    id: int
    status: Literal["pending", "completed", "failed"]
    user: MessageOut
    bot: Optional[MessageOut] = None


class ChatQueuedResponse(BaseModel):
    user: MessageOut
    pending_reply_id: int


class N8nCallbackPayload(BaseModel):
    message_id: int = Field(..., description="Identifiant du message utilisateur d’origine.")
    reply: str = Field(..., description="Texte retourné par n8n.")
    author: str | None = Field(default="n8n", description="Auteur à afficher pour la réponse.")

