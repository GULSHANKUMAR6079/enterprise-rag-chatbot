"""
Admin Ingestion & Management Endpoints.
Strictly protected by Admin role verification.
"""
import hashlib
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.permissions import UserRole, get_current_user_role, has_sufficient_role
from backend.app.db.models import Document, DocumentChunk
from backend.app.db.session import get_db
from backend.app.llm.gateway import llm_gateway
from backend.app.rag.chunker import semantic_chunker
from backend.app.rag.indirect_injection_defense import indirect_injection_defense
from backend.app.retrieval.bm25_retriever import bm25_retriever
from backend.app.retrieval.vector_store import VectorDocument, vector_store

router = APIRouter(prefix="/admin", tags=["Admin"])


class IngestDocumentRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10)
    source_url: str = Field(default="")
    category: str = Field(default="general")
    version: str = Field(default="1.0")


class IngestionReport(BaseModel):
    success: bool
    document_id: str
    chunks_created: int
    checksum: str
    indirect_injections_quarantined: int
    message: str


@router.post("/ingest", response_model=IngestionReport)
async def ingest_document(
    payload: IngestDocumentRequest,
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db)
) -> IngestionReport:
    """
    Admin-only document ingestion pipeline.
    Validates, chunks, scans for indirect injection, embeds, and indexes into hybrid store.
    """
    if not has_sufficient_role(user_role, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative authorization required to access knowledge ingestion."
        )

    # 1. Compute SHA-256 checksum
    checksum = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()

    # 2. Check for duplicate document
    existing_doc_res = await db.execute(
        select(Document).where(Document.checksum == checksum, Document.is_active == True)
    )
    existing_doc = existing_doc_res.scalars().first()
    if existing_doc:
        return IngestionReport(
            success=True,
            document_id=existing_doc.id,
            chunks_created=0,
            checksum=checksum,
            indirect_injections_quarantined=0,
            message="Document with identical checksum already ingested and active."
        )

    # 3. Create document record
    doc = Document(
        title=payload.title,
        source_url=payload.source_url,
        category=payload.category,
        version=payload.version,
        checksum=checksum,
        trust_level="trusted",
        is_active=True
    )
    db.add(doc)
    await db.flush()

    # 4. Semantic Chunker
    base_meta = {
        "document_id": doc.id,
        "title": doc.title,
        "source_url": doc.source_url,
        "category": doc.category,
        "version": doc.version
    }
    raw_chunks = semantic_chunker.chunk_document(payload.content, base_meta)

    # 5. Scan each chunk for indirect prompt injection
    quarantined_count = 0
    clean_chunk_texts = []
    processed_chunks = []

    for c in raw_chunks:
        risk_score, clean_text, findings = indirect_injection_defense.inspect_chunk(c.content)
        if risk_score > 0.0:
            quarantined_count += 1
        clean_chunk_texts.append(clean_text)
        processed_chunks.append((c, clean_text, risk_score))

    # 6. Generate Vector Embeddings in Batch
    embeddings = await llm_gateway.embed(clean_chunk_texts)

    # 7. Persist chunks to DB and Hybrid in-memory store
    bm25_corpus_update = {}
    for idx, (c, clean_text, risk_score) in enumerate(processed_chunks):
        embedding_vec = embeddings[idx] if idx < len(embeddings) else []

        db_chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=c.chunk_index,
            content=clean_text,
            token_count=c.token_estimate,
            embedding_json=embedding_vec,
            chunk_metadata=c.metadata,
            injection_risk_score=risk_score
        )
        db.add(db_chunk)
        await db.flush()

        # Add to Vector Store
        vector_doc = VectorDocument(
            chunk_id=db_chunk.id,
            document_id=doc.id,
            content=clean_text,
            embedding=embedding_vec,
            metadata=c.metadata,
            trust_level=doc.trust_level,
            injection_risk_score=risk_score
        )
        vector_store.add_document(vector_doc)
        bm25_corpus_update[db_chunk.id] = clean_text

    # Update BM25 Index
    current_docs = dict(bm25_retriever.documents)
    current_docs.update(bm25_corpus_update)
    bm25_retriever.index_documents(current_docs)

    await db.commit()

    return IngestionReport(
        success=True,
        document_id=doc.id,
        chunks_created=len(processed_chunks),
        checksum=checksum,
        indirect_injections_quarantined=quarantined_count,
        message=f"Successfully ingested '{doc.title}' with {len(processed_chunks)} chunks."
    )


class ScrapeUrlRequest(BaseModel):
    url: str = Field(description="Target HTTPS webpage to scrape and ingest")
    category: str = Field(default="website", description="Knowledge category tag")
    version: str = Field(default="1.0")


@router.post("/scrape-url", response_model=IngestionReport)
async def scrape_and_ingest_url(
    payload: ScrapeUrlRequest,
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db)
) -> IngestionReport:
    """
    Scrapes a webpage over HTTPS, strips scripts/nav/footer, screens for indirect injections,
    and ingests it directly into the hybrid RAG store.
    Guarded by full SSRF protection (rejects localhost, private IPs, cloud metadata).
    """
    if not has_sufficient_role(user_role, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative authorization required to scrape and ingest URLs."
        )

    from backend.app.rag.web_scraper import web_scraper

    # Scrape webpage with SSRF protection
    try:
        title, clean_content = await web_scraper.scrape_url(payload.url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to scrape URL: {exc}"
        )

    # Delegate to core document ingestion logic
    doc_payload = IngestDocumentRequest(
        title=title,
        content=clean_content,
        source_url=payload.url,
        category=payload.category,
        version=payload.version
    )
    return await ingest_document(payload=doc_payload, user_role=user_role, db=db)


class BatchIngestRequest(BaseModel):
    documents: List[IngestDocumentRequest]


@router.post("/ingest-batch")
async def ingest_batch_documents(
    payload: BatchIngestRequest,
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Batch ingestion endpoint for CI/CD pipelines, Git syncs, and CMS webhooks.
    """
    if not has_sufficient_role(user_role, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative authorization required for batch ingestion."
        )

    reports = []
    for doc_req in payload.documents:
        rep = await ingest_document(payload=doc_req, user_role=user_role, db=db)
        reports.append(rep)

    return {
        "success": True,
        "total_processed": len(payload.documents),
        "reports": reports
    }


class CrawlWebsiteRequest(BaseModel):
    root_url: str = Field(description="Target company website root URL (e.g. https://mycompany.com)")
    max_pages: int = Field(default=50, ge=1, le=200)
    max_depth: int = Field(default=3, ge=0, le=5)
    force_reindex: bool = Field(default=False)


@router.post("/crawl-website")
async def crawl_website_endpoint(
    payload: CrawlWebsiteRequest,
    user_role: str = Depends(get_current_user_role)
) -> Dict[str, Any]:
    """
    Triggers recursive crawler and incremental synchronization for a company website.
    """
    if not has_sufficient_role(user_role, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative authorization required to trigger crawler."
        )

    from backend.app.rag.website_crawler import website_crawler
    website_crawler.max_pages = payload.max_pages
    website_crawler.max_depth = payload.max_depth

    report = await website_crawler.crawl_and_sync(
        root_url=payload.root_url,
        force_reindex=payload.force_reindex
    )
    return report


