"""
Enterprise Website Assistant - FastAPI Application Entrypoint.
Coordinates security middleware, centralized exception handling, database initialization,
and modular API routing.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.chat import router as chat_router
from backend.app.api.v1.conversations import router as conversations_router
from backend.app.api.v1.feedback import router as feedback_router
from backend.app.api.v1.health import router as health_router
from backend.app.core.config import settings
from backend.app.core.exceptions import (
    ChatbotBaseException,
    chatbot_exception_handler,
    global_exception_handler
)
from backend.app.core.middleware import (
    PayloadSizeLimitMiddleware,
    RequestCorrelationMiddleware,
    SecurityHeadersMiddleware
)
from backend.app.db.session import init_db
from backend.app.gateway.rate_limiter import rate_limiter
from backend.app.observability.logger import app_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for database initialization and connection warm-up."""
    app_logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [Env: {settings.APP_ENV}]"
    )
    # 1. Initialize DB tables
    await init_db()

    # 2. Warm up Rate Limiter
    await rate_limiter.initialize()

    # 3. Warm up Vector Store & BM25 Retriever from database
    try:
        from sqlalchemy import select
        from backend.app.db.models import Document, DocumentChunk
        from backend.app.db.session import AsyncSessionLocal
        from backend.app.retrieval.bm25_retriever import bm25_retriever
        from backend.app.retrieval.vector_store import VectorDocument, vector_store

        async with AsyncSessionLocal() as db:
            query = (
                select(DocumentChunk, Document)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(DocumentChunk.is_active == True, Document.is_active == True)
            )
            rows = (await db.execute(query)).all()
            bm25_batch = {}
            for chunk, doc in rows:
                vdoc = VectorDocument(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    content=chunk.content,
                    embedding=chunk.embedding_json or [],
                    metadata=chunk.chunk_metadata or {"title": doc.title, "source_url": doc.source_url},
                    trust_level=doc.trust_level,
                    injection_risk_score=chunk.injection_risk_score
                )
                vector_store.add_document(vdoc)
                bm25_batch[chunk.id] = chunk.content
            if bm25_batch:
                bm25_retriever.index_documents(bm25_batch)
                app_logger.info(f"Loaded {len(bm25_batch)} active knowledge chunks into hybrid retrieval indexes.")
    except Exception as exc:
        app_logger.warning(f"Could not preload knowledge base on startup: {exc}")

    yield

    # Cleanup on shutdown
    app_logger.info("Shutting down application and closing network connections...")
    await rate_limiter.close()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
        lifespan=lifespan
    )

    # Attach state flags
    app.state.debug = settings.DEBUG

    # 1. Register Security Middlewares (Order: Payload -> RequestID -> Headers -> CORS)
    app.add_middleware(PayloadSizeLimitMiddleware)
    app.add_middleware(RequestCorrelationMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. CORS Configuration (Strict Origins, no wildcard in production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        max_age=600
    )

    # 3. Exception Handlers
    app.add_exception_handler(ChatbotBaseException, chatbot_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # 4. Include Routers
    api_v1_prefix = "/api/v1"
    app.include_router(chat_router, prefix=api_v1_prefix)
    app.include_router(conversations_router, prefix=api_v1_prefix)
    app.include_router(feedback_router, prefix=api_v1_prefix)
    app.include_router(admin_router, prefix=api_v1_prefix)
    app.include_router(health_router)

    return app


app = create_application()
