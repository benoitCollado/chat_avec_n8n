from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .security import hash_password, verify_password


def create_user(session: Session, user_in: schemas.UserCreate) -> models.User:
    user = models.User(
        email=user_in.email.lower(),
        full_name=user_in.full_name,
        hashed_password=hash_password(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_email(session: Session, email: str) -> models.User | None:
    stmt = select(models.User).where(models.User.email == email.lower())
    return session.execute(stmt).scalar_one_or_none()


def authenticate_user(session: Session, email: str, password: str) -> models.User | None:
    user = get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_message(session: Session, *, user: models.User, author: str, content: str, direction: str) -> models.Message:
    message = models.Message(author=author, content=content, direction=direction, user=user)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_messages(session: Session, user: models.User, limit: int = 50) -> list[models.Message]:
    stmt = (
        select(models.Message)
        .where(models.Message.user_id == user.id)
        .order_by(models.Message.created_at.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).scalars().all()
    # Retourner dans l’ordre chronologique
    return list(reversed(rows))


def delete_message(session: Session, message: models.Message) -> None:
    session.delete(message)
    session.commit()


def get_pending_reply_by_user(session: Session, user: models.User, *, only_pending: bool = True) -> models.PendingReply | None:
    stmt = select(models.PendingReply).where(models.PendingReply.user_id == user.id)
    if only_pending:
        stmt = stmt.where(models.PendingReply.status == "pending")
    stmt = stmt.order_by(models.PendingReply.created_at.desc())
    return session.execute(stmt).scalars().first()


def get_pending_reply_by_id(
    session: Session, pending_id: int, user: models.User | None = None
) -> models.PendingReply | None:
    stmt = select(models.PendingReply).where(models.PendingReply.id == pending_id)
    if user:
        stmt = stmt.where(models.PendingReply.user_id == user.id)
    return session.execute(stmt).scalar_one_or_none()


def create_pending_reply(session: Session, user: models.User, user_message: models.Message) -> models.PendingReply:
    pending = models.PendingReply(user=user, user_message=user_message, status="pending")
    session.add(pending)
    session.commit()
    session.refresh(pending)
    return pending


def complete_pending_reply(
    session: Session, pending: models.PendingReply, bot_message: models.Message, status: str = "completed"
) -> models.PendingReply:
    pending.bot_message_id = bot_message.id
    pending.status = status
    session.add(pending)
    session.commit()
    session.refresh(pending)
    return pending


def fail_pending_reply(session: Session, pending: models.PendingReply) -> models.PendingReply:
    pending.status = "failed"
    session.add(pending)
    session.commit()
    session.refresh(pending)
    return pending


def delete_pending_reply(session: Session, pending: models.PendingReply) -> None:
    session.delete(pending)
    session.commit()


def get_pending_reply_by_message_id(session: Session, message_id: int) -> models.PendingReply | None:
    stmt = select(models.PendingReply).where(models.PendingReply.user_message_id == message_id)
    return session.execute(stmt).scalar_one_or_none()

