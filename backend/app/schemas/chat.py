"""
Pydantic Schemas for Chat API.
Strict validation preventing arbitrary deserialization and bounding message lengths.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


class SourceCitation(BaseModel):
    """Grounding source citation returned to the frontend."""
    id: str = Field(description="Citation index or chunk ID")
    title: str = Field(description="Document title")
    url: Optional[str] = Field(default=None, description="Approved public URL")
    category: Optional[str] = Field(default="Documentation")


class ChatRequest(BaseModel):
    """Incoming user chat request."""
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Existing conversation ID. If omitted, a new conversation is initialized."
    )
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="User prompt text"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response via SSE"
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Message cannot be empty or purely whitespace.")
        return trimmed


class ChatResponse(BaseModel):
    """
    Standardized response format.
    Never exposes internal system prompts, security scores, or model chain-of-thought.
    """
    request_id: str
    conversation_id: str
    answer: str
    sources: List[SourceCitation] = Field(default_factory=list)
    confidence: Literal["grounded", "partially_grounded", "insufficient_evidence"] = "grounded"


class StreamChunk(BaseModel):
    """Event structure for Server-Sent Events (SSE) streaming."""
    event: Literal["token", "citation", "done", "error"]
    data: Dict[str, Any]
