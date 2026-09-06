"""
Knowledge Ingestion CLI Pipeline.
Loads markdown documentation, computes checksums, applies semantic chunking,
screens for indirect prompt injection, embeds chunks, and populates the hybrid retrieval indexes.
"""
import argparse
import asyncio
import hashlib
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.db.models import Document, DocumentChunk
from backend.app.db.session import AsyncSessionLocal, init_db
from backend.app.llm.gateway import llm_gateway
from backend.app.rag.chunker import semantic_chunker
from backend.app.rag.indirect_injection_defense import indirect_injection_defense
from backend.app.retrieval.bm25_retriever import bm25_retriever
from backend.app.retrieval.vector_store import VectorDocument, vector_store


async def ingest_directory(data_dir: str):
    print(f"[*] Initializing database tables...")
    await init_db()

    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"[!] Error: Directory '{data_dir}' does not exist.")
        return

    doc_files = list(data_path.glob("*.md")) + list(data_path.glob("*.txt"))
    print(f"[*] Found {len(doc_files)} knowledge documents in '{data_dir}'")

    total_chunks = 0
    total_quarantined = 0
    bm25_batch = {}

    async with AsyncSessionLocal() as db:
        for file_path in doc_files:
            content = file_path.read_text(encoding="utf-8")
            title = file_path.stem.replace("_", " ").title()
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

            # Create or update document
            doc = Document(
                title=title,
                source_url=f"https://docs.incerro.example.com/{file_path.name}",
                category="knowledge_base",
                version="1.0",
                checksum=checksum,
                trust_level="trusted",
                is_active=True
            )
            db.add(doc)
            await db.flush()

            # Semantic chunking
            meta = {
                "document_id": doc.id,
                "title": doc.title,
                "source_url": doc.source_url,
                "category": doc.category,
                "version": doc.version
            }
            chunks = semantic_chunker.chunk_document(content, meta)

            clean_texts = []
            chunk_records = []
            for c in chunks:
                risk, clean_text, findings = indirect_injection_defense.inspect_chunk(c.content)
                if risk > 0.0:
                    total_quarantined += 1
                clean_texts.append(clean_text)
                chunk_records.append((c, clean_text, risk))

            # Batch embed
            embeddings = await llm_gateway.embed(clean_texts)

            for idx, (c, clean_text, risk) in enumerate(chunk_records):
                vec = embeddings[idx] if idx < len(embeddings) else []
                db_chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=c.chunk_index,
                    content=clean_text,
                    token_count=c.token_estimate,
                    embedding_json=vec,
                    chunk_metadata=c.metadata,
                    injection_risk_score=risk
                )
                db.add(db_chunk)
                await db.flush()

                # Add to Vector Store
                vdoc = VectorDocument(
                    chunk_id=db_chunk.id,
                    document_id=doc.id,
                    content=clean_text,
                    embedding=vec,
                    metadata=c.metadata,
                    trust_level=doc.trust_level,
                    injection_risk_score=risk
                )
                vector_store.add_document(vdoc)
                bm25_batch[db_chunk.id] = clean_text
                total_chunks += 1

            print(f"  [+] Ingested '{title}' ({len(chunk_records)} chunks)")

        await db.commit()

    # Index into BM25 retriever
    bm25_retriever.index_documents(bm25_batch)

    print("\n" + "=" * 50)
    print("INGESTION REPORT")
    print("=" * 50)
    print(f"Documents Ingested:             {len(doc_files)}")
    print(f"Total Chunks Created:           {total_chunks}")
    print(f"Indirect Injections Screened:   {total_quarantined}")
    print(f"Active Vector Chunks in Memory: {vector_store.count()}")
    print("=" * 50)


async def scrape_and_ingest_single_url(target_url: str, category: str = "website"):
    from backend.app.rag.web_scraper import web_scraper
    print(f"[*] Fetching and scraping URL: {target_url}...")
    try:
        title, clean_content = await web_scraper.scrape_url(target_url)
        print(f"  [+] Extracted page: '{title}' ({len(clean_content)} characters)")
    except Exception as exc:
        print(f"  [!] Failed to scrape URL: {exc}")
        return

    await init_db()
    checksum = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()

    async with AsyncSessionLocal() as db:
        doc = Document(
            title=title,
            source_url=target_url,
            category=category,
            version="1.0",
            checksum=checksum,
            trust_level="trusted",
            is_active=True
        )
        db.add(doc)
        await db.flush()

        meta = {
            "document_id": doc.id,
            "title": doc.title,
            "source_url": target_url,
            "category": category,
            "version": "1.0"
        }
        chunks = semantic_chunker.chunk_document(clean_content, meta)
        clean_texts = []
        chunk_records = []
        quarantined = 0

        for c in chunks:
            risk, clean_text, findings = indirect_injection_defense.inspect_chunk(c.content)
            if risk > 0.0:
                quarantined += 1
            clean_texts.append(clean_text)
            chunk_records.append((c, clean_text, risk))

        embeddings = await llm_gateway.embed(clean_texts)
        bm25_batch = {}

        for idx, (c, clean_text, risk) in enumerate(chunk_records):
            vec = embeddings[idx] if idx < len(embeddings) else []
            db_chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=c.chunk_index,
                content=clean_text,
                token_count=c.token_estimate,
                embedding_json=vec,
                chunk_metadata=c.metadata,
                injection_risk_score=risk
            )
            db.add(db_chunk)
            await db.flush()

            vdoc = VectorDocument(
                chunk_id=db_chunk.id,
                document_id=doc.id,
                content=clean_text,
                embedding=vec,
                metadata=c.metadata,
                trust_level="trusted",
                injection_risk_score=risk
            )
            vector_store.add_document(vdoc)
            bm25_batch[db_chunk.id] = clean_text

        current_docs = dict(bm25_retriever.documents)
        current_docs.update(bm25_batch)
        bm25_retriever.index_documents(current_docs)

        await db.commit()

        print(f"  [+] Ingested '{title}' into RAG ({len(chunk_records)} chunks, {quarantined} quarantined)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest company knowledge via files or web scraping.")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to directory containing markdown/txt documents"
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Target HTTPS webpage URL to scrape, sanitize, and ingest into RAG"
    )
    args = parser.parse_args()

    if args.url:
        asyncio.run(scrape_and_ingest_single_url(args.url))
    else:
        target_dir = args.data_dir or os.path.join(os.path.dirname(__file__), "sample_knowledge")
        asyncio.run(ingest_directory(target_dir))

