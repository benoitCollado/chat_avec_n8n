import json
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .crud import authenticate_user, create_message, create_user, get_user_by_email, list_messages
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


@api_router.post("/chat", response_model=schemas.ChatResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: schemas.ChatRequest,
    session: Session = Depends(get_session),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ChatResponse:
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Utilisateur invalide pour ce token.")

    inbound = create_message(
        session,
        user=current_user,
        author=current_user.full_name,
        content=payload.content,
        direction="user",
    )

    try:
        webhook_response = await forward_to_n8n(payload.model_dump())
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    reply_text = (
        webhook_response.get("reply")
        or webhook_response.get("message")
        or webhook_response.get("text")
        or json.dumps(webhook_response)
    )

    outbound = create_message(
        session,
        user=current_user,
        author="n8n",
        content=reply_text,
        direction="n8n",
    )

    return schemas.ChatResponse(
        user=schemas.MessageOut.model_validate(inbound),
        bot=schemas.MessageOut.model_validate(outbound),
        raw_webhook_response=webhook_response,
    )


app.include_router(api_router)

