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

