"""
Conversation Lifecycle Endpoints.
Allows frontend to create, list, inspect, and delete conversations bound to the session.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_session_context
from backend.app.db.models import Conversation, Message, Session
from backend.app.db.session import get_db
from backend.app.schemas.chat import SourceCitation
from backend.app.schemas.conversation import ConversationListResponse, ConversationResponse, MessageItem

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    conv = Conversation(session_id=session.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db)
) -> ConversationListResponse:
    query = (
        select(Conversation)
        .where(Conversation.session_id == session.id, Conversation.is_archived == False)
        .order_by(Conversation.updated_at.desc())
    )
    res = await db.execute(query)
    conversations = res.scalars().all()
    return ConversationListResponse(
        conversations=[
            ConversationResponse(
                id=c.id,
                title=c.title,
                message_count=c.message_count,
                created_at=c.created_at,
                updated_at=c.updated_at
            )
            for c in conversations
        ]
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.session_id == session.id)
    )
    res = await db.execute(query)
    conv = res.scalars().first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Load messages
    msg_query = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
    )
    msg_res = await db.execute(msg_query)
    messages = msg_res.scalars().all()

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        message_count=conv.message_count,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=[SourceCitation(**c) for c in (m.citations or [])],
                confidence=m.confidence,
                created_at=m.created_at
            )
            for m in messages
        ]
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db)
) -> dict:
    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.session_id == session.id)
    )
    res = await db.execute(query)
    conv = res.scalars().first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"success": True, "message": "Conversation deleted successfully."}
