from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


def create_message(session: Session, *, author: str, content: str, direction: str) -> models.Message:
    message = models.Message(author=author, content=content, direction=direction)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def list_messages(session: Session, limit: int = 50) -> list[models.Message]:
    stmt = select(models.Message).order_by(models.Message.created_at.desc()).limit(limit)
    rows = session.execute(stmt).scalars().all()
    # Retourner dans l’ordre chronologique
    return list(reversed(rows))

