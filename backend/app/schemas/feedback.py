"""
Pydantic Schemas for Feedback and Health Check APIs.
"""
from typing import Optional, Dict, Literal
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    message_id: str = Field(description="Message UUID to attach feedback to")
    rating: int = Field(ge=-1, le=1, description="1 for helpful, -1 for unhelpful")
    comment: Optional[str] = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    success: bool
    feedback_id: str
    message: str = "Feedback received successfully."


class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    version: str


class ReadinessStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["connected", "error"]
    redis: Literal["connected", "fallback", "error"]
    llm_gateway: Literal["ready", "circuit_open", "error"]
