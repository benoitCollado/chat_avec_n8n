import json
from typing import Any, Dict

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .crud import create_message, list_messages
from .database import Base, engine, get_session
from .schemas import ChatRequest, ChatResponse, HistoryResponse, MessageOut


Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/messages", response_model=HistoryResponse)
def get_messages(limit: int = 50, session: Session = Depends(get_session)) -> HistoryResponse:
    messages = list_messages(session, limit=limit)
    return HistoryResponse(messages=[MessageOut.model_validate(m) for m in messages])


@app.post("/chat", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: ChatRequest,
    session: Session = Depends(get_session),
) -> ChatResponse:
    inbound = create_message(session, author=payload.author, content=payload.content, direction="user")

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

    outbound = create_message(session, author="n8n", content=reply_text, direction="n8n")

    return ChatResponse(
        user=MessageOut.model_validate(inbound),
        bot=MessageOut.model_validate(outbound),
        raw_webhook_response=webhook_response,
    )

