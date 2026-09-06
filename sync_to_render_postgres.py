"""
One-Time Sync: Copies all 54 webscraped documents and 385 chunks from local chatbot.db
directly into Render's cloud PostgreSQL database.
"""
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.app.db.models import Document, DocumentChunk
from backend.app.db.session import AsyncSessionLocal, init_db


async def migrate_to_postgres():
    print("\n" + "=" * 60)
    print("[*] STARTING MIGRATION: Local chatbot.db -> Render PostgreSQL")
    print("=" * 60)

    # 1. Initialize PostgreSQL schema
    print("[1/3] Initializing tables in Render PostgreSQL...")
    await init_db()

    # 2. Read from local SQLite
    print("[2/3] Reading webscraped data from local chatbot.db...")
    sqlite_path = "chatbot.db"
    if not os.path.exists(sqlite_path):
        print(f"[!] Error: {sqlite_path} not found!")
        return

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    docs = c.execute("SELECT * FROM documents").fetchall()
    chunks = c.execute("SELECT * FROM document_chunks").fetchall()

    print(f"[*] Found {len(docs)} scraped web pages and {len(chunks)} chunks in local SQLite.")

    # 3. Batch insert into Render PostgreSQL
    print("[3/3] Uploading all records into Render PostgreSQL...")
    async with AsyncSessionLocal() as db:
        for d in docs:
            doc_obj = Document(
                id=d["id"],
                title=d["title"],
                source_url=d["source_url"],
                category=d["category"],
                version=d["version"],
                checksum=d["checksum"],
                trust_level=d["trust_level"],
                is_active=bool(d["is_active"])
            )
            db.add(doc_obj)
        await db.flush()

        for ch in chunks:
            raw_emb = ch["embedding_json"]
            raw_meta = ch["chunk_metadata"]
            
            emb = json.loads(raw_emb) if isinstance(raw_emb, str) else raw_emb
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta

            chunk_obj = DocumentChunk(
                id=ch["id"],
                document_id=ch["document_id"],
                chunk_index=ch["chunk_index"],
                content=ch["content"],
                token_count=ch["token_count"],
                embedding_json=emb or [],
                chunk_metadata=meta or {},
                injection_risk_score=ch["injection_risk_score"] or 0.0,
                is_active=bool(ch["is_active"])
            )
            db.add(chunk_obj)

        await db.commit()

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Migrated {len(docs)} web pages & {len(chunks)} chunks into Render PostgreSQL!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(migrate_to_postgres())
