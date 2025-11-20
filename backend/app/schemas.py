from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    author: str = Field(..., description="Nom lisible de l’émetteur")
    content: str = Field(..., description="Contenu textuel du message")
    direction: str = Field(..., description="user ou n8n")


class MessageOut(MessageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    author: str = Field(..., examples=["Utilisateur"])
    content: str = Field(..., examples=["Bonjour n8n"])


class ChatResponse(BaseModel):
    user: MessageOut
    bot: MessageOut
    raw_webhook_response: Optional[dict] = None


class HistoryResponse(BaseModel):
    messages: List[MessageOut]

