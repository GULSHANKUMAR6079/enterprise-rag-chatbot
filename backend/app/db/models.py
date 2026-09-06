"""
SQLAlchemy Models for Enterprise Chatbot.
Covers users, sessions, conversations, messages, documents, chunks, feedback, LLM metrics, and security audit events.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum, Index
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=True)
    role = Column(String(50), default="public", index=True)  # public, employee, support, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_token = Column(String(128), unique=True, index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_hash = Column(String(64), index=True, nullable=False)
    user_agent = Column(String(512), nullable=True)
    abuse_score = Column(Integer, default=0)
    is_blocked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session", cascade="all, delete-orphan")
    security_events = relationship("SecurityEvent", back_populates="session")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(255), default="New Conversation")
    message_count = Column(Integer, default=0)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    session = relationship("Session", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    citations = Column(JSON, default=list)  # List of source metadata [{title, url, chunk_id}]
    confidence = Column(String(30), default="grounded")  # grounded, partially_grounded, insufficient_evidence
    created_at = Column(DateTime(timezone=True), default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")
    feedback = relationship("Feedback", back_populates="message", uselist=False, cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    source_url = Column(String(1024), nullable=True)
    category = Column(String(100), default="general")  # company, product, faq, pricing, legal
    version = Column(String(50), default="1.0")
    checksum = Column(String(64), nullable=False, index=True)  # SHA-256
    trust_level = Column(String(20), default="trusted")  # trusted, internal, public, untrusted
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    embedding_json = Column(JSON, nullable=True)  # Stored vector for universal DB compatibility
    chunk_metadata = Column(JSON, default=dict)  # Header path, category, permissions
    injection_risk_score = Column(Float, default=0.0)  # 0.0 (safe) to 1.0 (malicious)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("Document", back_populates="chunks")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False)
    rating = Column(Integer, nullable=False)  # 1 for positive, -1 for negative
    comment = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    message = relationship("Message", back_populates="feedback")


class LLMRequest(Base):
    __tablename__ = "llm_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    request_id = Column(String(64), index=True, nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    latency_ms = Column(Float, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    status = Column(String(30), default="success")  # success, fallback, error, timeout
    created_at = Column(DateTime(timezone=True), default=utc_now)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # prompt_injection, secret_leak, pii_detected, rate_limit, ssrf_attempt
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    request_id = Column(String(64), index=True, nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("Session", back_populates="security_events")
