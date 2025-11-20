from datetime import datetime
from typing import List, Optional

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


class ChatResponse(BaseModel):
    user: MessageOut
    bot: MessageOut
    raw_webhook_response: Optional[dict] = None


class HistoryResponse(BaseModel):
    messages: List[MessageOut]

