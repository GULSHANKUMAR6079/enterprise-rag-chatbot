"""
Pydantic Schemas for Conversation Management.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.chat import SourceCitation


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    citations: List[SourceCitation] = Field(default_factory=list)
    confidence: Optional[str] = "grounded"
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[MessageItem]] = None


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
