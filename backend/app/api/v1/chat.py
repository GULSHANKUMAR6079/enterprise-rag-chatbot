"""
Chat API Endpoints.
Provides standard JSON and streaming (SSE) response modes.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import enforce_rate_limits, get_session_context
from backend.app.auth.permissions import get_current_user_role
from backend.app.db.models import Session
from backend.app.db.session import get_db
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, dependencies=[Depends(enforce_rate_limits)])
async def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(get_current_user_role)
) -> ChatResponse:
    """
    Standard synchronous chat completion endpoint.
    All messages pass through the multi-layer security guardrails and hybrid RAG engine.
    """
    request_id = getattr(request.state, "request_id", "req-unknown")
    return await chat_service.process_chat(
        user_message=payload.message,
        conversation_id=payload.conversation_id,
        session=session,
        db=db,
        request_id=request_id,
        user_role=user_role
    )


@router.post("/stream", dependencies=[Depends(enforce_rate_limits)])
async def chat_stream_endpoint(
    request: Request,
    payload: ChatRequest,
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(get_current_user_role)
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) streaming chat endpoint.
    Streams incremental tokens with safety checks and concludes with grounding citations.
    """
    request_id = getattr(request.state, "request_id", "req-unknown")
    event_generator = chat_service.stream_chat(
        user_message=payload.message,
        conversation_id=payload.conversation_id,
        session=session,
        db=db,
        request_id=request_id,
        user_role=user_role
    )

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
