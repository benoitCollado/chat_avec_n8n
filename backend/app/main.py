from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .crud import (
    authenticate_user,
    complete_pending_reply,
    create_message,
    create_pending_reply,
    create_user,
    delete_message,
    delete_pending_reply,
    fail_pending_reply,
    get_pending_reply_by_id,
    get_pending_reply_by_message_id,
    get_pending_reply_by_user,
    get_user_by_email,
    list_messages,
)
from .database import Base, engine, get_session
from .security import create_access_token, create_refresh_token, decode_token, get_current_user


Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
api_router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins or ["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def forward_to_n8n(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.n8n_webhook_url:
        raise HTTPException(status_code=500, detail="La variable N8N_WEBHOOK_URL n’est pas configurée.")

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.post(settings.n8n_webhook_url, json=payload)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur du webhook n8n: {exc.response.text}") from exc

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()

    return {"reply": response.text}


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def issue_tokens(user: models.User) -> schemas.TokenPair:
    return schemas.TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=schemas.UserOut.model_validate(user),
    )


@api_router.post("/auth/register", response_model=schemas.TokenPair, status_code=status.HTTP_201_CREATED)
def register_user(payload: schemas.UserCreate, session: Session = Depends(get_session)) -> schemas.TokenPair:
    if get_user_by_email(session, payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet email est déjà utilisé.")
    user = create_user(session, payload)
    return issue_tokens(user)


@api_router.post("/auth/login", response_model=schemas.TokenPair)
def login(payload: schemas.UserLogin, session: Session = Depends(get_session)) -> schemas.TokenPair:
    user = authenticate_user(session, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides.")
    return issue_tokens(user)


@api_router.post("/auth/refresh", response_model=schemas.TokenPair)
def refresh(payload: schemas.RefreshRequest, session: Session = Depends(get_session)) -> schemas.TokenPair:
    token_data = decode_token(payload.refresh_token, expected_type="refresh")
    user = session.get(models.User, int(token_data["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return issue_tokens(user)


@api_router.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)) -> schemas.UserOut:
    return schemas.UserOut.model_validate(current_user)


@api_router.get("/messages", response_model=schemas.HistoryResponse)
def get_messages(
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(get_current_user),
) -> schemas.HistoryResponse:
    messages = list_messages(session, user=current_user, limit=limit)
    return schemas.HistoryResponse(messages=[schemas.MessageOut.model_validate(m) for m in messages])


def serialize_pending(pending: models.PendingReply) -> schemas.PendingStatusResponse:
    return schemas.PendingStatusResponse(
        id=pending.id,
        status=pending.status,
        user=schemas.MessageOut.model_validate(pending.user_message),
        bot=schemas.MessageOut.model_validate(pending.bot_message) if pending.bot_message else None,
    )


@api_router.post("/chat", response_model=schemas.ChatQueuedResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: schemas.ChatRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ChatQueuedResponse:
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Utilisateur invalide pour ce token.")

    existing_pending = get_pending_reply_by_user(session, current_user, only_pending=False)
    if existing_pending:
        # Si le pending est en erreur, on le supprime immédiatement pour permettre un nouvel envoi
        if existing_pending.status == "failed":
            delete_pending_reply(session, existing_pending)
        # Si le pending est plus ancien que 60 secondes, on le supprime pour permettre un nouvel envoi
        else:
            now = datetime.now(timezone.utc)
            # S'assurer que created_at est timezone-aware
            pending_created_at = existing_pending.created_at
            if pending_created_at.tzinfo is None:
                pending_created_at = pending_created_at.replace(tzinfo=timezone.utc)
            pending_age = now - pending_created_at
            if pending_age > timedelta(seconds=60):
                delete_pending_reply(session, existing_pending)
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Une réponse est déjà en attente pour cet utilisateur."
                )

    inbound = create_message(
        session,
        user=current_user,
        author=current_user.full_name,
        content=payload.content,
        direction="user",
    )

    pending = create_pending_reply(session, current_user, inbound)

    try:
        payload_for_n8n = payload.model_dump()
        payload_for_n8n["message_id"] = inbound.id
        payload_for_n8n["pending_reply_id"] = pending.id
        await forward_to_n8n(payload_for_n8n)
    except (httpx.HTTPError, HTTPException) as exc:
        # En cas d'erreur, supprimer immédiatement le pending et le message pour permettre un nouvel envoi
        delete_pending_reply(session, pending)
        delete_message(session, inbound)
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return schemas.ChatQueuedResponse(
        user=schemas.MessageOut.model_validate(inbound),
        pending_reply_id=pending.id,
    )


@api_router.get("/chat/pending/{pending_id}", response_model=schemas.PendingStatusResponse)
def get_pending_status(
    pending_id: int,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PendingStatusResponse:
    pending = get_pending_reply_by_id(session, pending_id, current_user)
    if not pending:
        raise HTTPException(status_code=404, detail="Réponse en attente introuvable.")
    return serialize_pending(pending)


@api_router.get("/chat/pending", response_model=schemas.PendingStatusResponse)
def get_current_pending(
    session: Session = Depends(get_session),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PendingStatusResponse:
    pending = get_pending_reply_by_user(session, current_user, only_pending=True)
    if not pending:
        raise HTTPException(status_code=404, detail="Aucune réponse en attente.")
    return serialize_pending(pending)


@api_router.post("/chat/pending/{pending_id}/fail", response_model=schemas.PendingStatusResponse)
def fail_pending(
    pending_id: int,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PendingStatusResponse:
    pending = get_pending_reply_by_id(session, pending_id, current_user)
    if not pending:
        raise HTTPException(status_code=404, detail="Réponse en attente introuvable.")
    if pending.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce message a déjà été traité.")
    pending = fail_pending_reply(session, pending)
    return serialize_pending(pending)


@api_router.post("/chat/callback", response_model=schemas.PendingStatusResponse)
def receive_n8n_callback(
    payload: schemas.N8nCallbackPayload,
    session: Session = Depends(get_session),
    callback_token: str | None = Header(default=None, alias="X-Callback-Token"),
) -> schemas.PendingStatusResponse:
    if settings.n8n_callback_token and callback_token != settings.n8n_callback_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de callback invalide.")

    pending = get_pending_reply_by_message_id(session, payload.message_id)
    if not pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message utilisateur introuvable.")
    if pending.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce message a déjà été traité.")

    bot_message = create_message(
        session,
        user=pending.user,
        author=payload.author or "n8n",
        content=payload.reply,
        direction="n8n",
    )

    pending = complete_pending_reply(session, pending, bot_message)
    return serialize_pending(pending)


app.include_router(api_router)

