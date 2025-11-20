from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    messages: Mapped[list["Message"]] = relationship("Message", back_populates="user", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    user: Mapped[User] = relationship("User", back_populates="messages")


class PendingReply(Base):
    __tablename__ = "pending_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False, unique=True)
    bot_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped[User] = relationship("User")
    user_message: Mapped[Message] = relationship("Message", foreign_keys=[user_message_id])
    bot_message: Mapped[Message | None] = relationship("Message", foreign_keys=[bot_message_id])

