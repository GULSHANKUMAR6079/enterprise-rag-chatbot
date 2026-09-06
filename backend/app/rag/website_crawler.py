"""
Recursive Website Crawler and Incremental Synchronization Engine.
Crawls company websites, discovers pages via sitemaps and internal links,
cleans HTML, and performs incremental sync using SHA-256 content checksums.
"""
import asyncio
import hashlib
import logging
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag
import bs4
import httpx
from sqlalchemy import select

from backend.app.core.exceptions import SSRFBlockedException
from backend.app.db.models import Document, DocumentChunk
from backend.app.db.session import AsyncSessionLocal, init_db
from backend.app.llm.gateway import llm_gateway
from backend.app.rag.chunker import semantic_chunker
from backend.app.rag.indirect_injection_defense import indirect_injection_defense
from backend.app.rag.web_scraper import web_scraper
from backend.app.retrieval.bm25_retriever import bm25_retriever
from backend.app.retrieval.vector_store import VectorDocument, vector_store
from backend.app.security.ssrf_protector import ssrf_protector

logger = logging.getLogger("website_crawler")

# File extensions to ignore during crawling
IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".exe", ".dmg",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf"
)


class WebsiteCrawler:
    def __init__(
        self,
        max_pages: int = 50,
        max_depth: int = 3,
        request_timeout: float = 12.0
    ):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.request_timeout = request_timeout

    def normalize_url(self, url: str) -> str:
        """Strips fragments, query strings, and trailing slashes for clean canonical URLs."""
        clean, _ = urldefrag(url)
        parsed = urlparse(clean)
        # Rebuild without query params or fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        return normalized

    def is_same_domain(self, target_url: str, base_netloc: str) -> bool:
        """Ensures the crawler stays strictly bounded to the target company's domain."""
        try:
            parsed = urlparse(target_url)
            # Match exact domain or subdomains
            return parsed.netloc == base_netloc or parsed.netloc.endswith(f".{base_netloc}")
        except Exception:
            return False

    async def discover_sitemap_urls(self, base_url: str) -> List[str]:
        """Attempts to fetch sitemap.xml to discover canonical pages."""
        parsed = urlparse(base_url)
        sitemap_candidates = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
        ]
        discovered = []
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for sitemap_url in sitemap_candidates:
                try:
                    ssrf_protector.validate_url(sitemap_url)
                    resp = await client.get(sitemap_url)
                    if resp.status_code == 200 and ("xml" in resp.headers.get("Content-Type", "")):
                        soup = bs4.BeautifulSoup(resp.text, "xml")
                        locs = soup.find_all("loc")
                        for loc in locs:
                            u = loc.text.strip()
                            if not u.endswith(IGNORED_EXTENSIONS) and self.is_same_domain(u, parsed.netloc):
                                discovered.append(self.normalize_url(u))
                        if discovered:
                            logger.info(f"Discovered {len(discovered)} URLs via sitemap: {sitemap_url}")
                            break
                except Exception:
                    continue
        return list(set(discovered))

    async def crawl_and_sync(
        self,
        root_url: str,
        category: str = "website",
        force_reindex: bool = False
    ) -> Dict:
        """
        Crawls the website starting from root_url.
        Performs incremental sync:
        - Detects new pages -> ingests them
        - Detects changed pages (via SHA-256 checksum) -> re-chunks & re-indexes them
        - Detects unchanged pages -> skips re-embedding (zero cost)
        """
        await init_db()
        canonical_root = self.normalize_url(root_url)
        ssrf_protector.validate_url(canonical_root)
        base_netloc = urlparse(canonical_root).netloc

        queue: List[Tuple[str, int]] = [(canonical_root, 0)]
        visited: Set[str] = {canonical_root}
        discovered_urls: Set[str] = {canonical_root}

        # Step 1: Check sitemap
        sitemap_urls = await self.discover_sitemap_urls(canonical_root)
        for s_url in sitemap_urls:
            if s_url not in visited and len(discovered_urls) < self.max_pages:
                discovered_urls.add(s_url)
                queue.append((s_url, 1))

        # Metrics
        report = {
            "root_url": canonical_root,
            "total_pages_scanned": 0,
            "new_pages_ingested": 0,
            "pages_updated": 0,
            "pages_unchanged": 0,
            "total_chunks_indexed": 0,
            "quarantined_instructions": 0,
            "scanned_pages": []
        }

        # Step 2: Crawl queue
        while queue and report["total_pages_scanned"] < self.max_pages:
            current_url, depth = queue.pop(0)
            report["total_pages_scanned"] += 1

            try:
                # Scrape page text
                title, clean_text = await web_scraper.scrape_url(current_url, timeout=self.request_timeout)
            except Exception as exc:
                logger.warning(f"Skipping URL {current_url}: {exc}")
                continue

            # Compute SHA-256 content checksum
            content_checksum = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

            # Step 3: Incremental Sync Evaluation
            async with AsyncSessionLocal() as db:
                existing_doc_res = await db.execute(
                    select(Document).where(Document.source_url == current_url, Document.is_active == True)
                )
                existing_doc = existing_doc_res.scalars().first()

                if existing_doc and existing_doc.checksum == content_checksum and not force_reindex:
                    # Page is identical: skip re-embedding
                    report["pages_unchanged"] += 1
                    report["scanned_pages"].append({
                        "url": current_url,
                        "title": title,
                        "status": "unchanged"
                    })
                else:
                    # Brand new or modified page
                    is_update = existing_doc is not None
                    if is_update:
                        # Deactivate previous chunks
                        old_chunks_res = await db.execute(
                            select(DocumentChunk).where(DocumentChunk.document_id == existing_doc.id)
                        )
                        for old_c in old_chunks_res.scalars().all():
                            old_c.is_active = False
                        existing_doc.checksum = content_checksum
                        existing_doc.title = title
                        target_doc = existing_doc
                        report["pages_updated"] += 1
                    else:
                        target_doc = Document(
                            title=title,
                            source_url=current_url,
                            category=category,
                            version="1.0",
                            checksum=content_checksum,
                            trust_level="trusted",
                            is_active=True
                        )
                        db.add(target_doc)
                        await db.flush()
                        report["new_pages_ingested"] += 1

                    # Semantic Chunking
                    meta = {
                        "document_id": target_doc.id,
                        "title": title,
                        "source_url": current_url,
                        "category": category,
                        "version": "1.0"
                    }
                    raw_chunks = semantic_chunker.chunk_document(clean_text, meta)
                    clean_chunk_texts = []
                    chunk_meta_list = []

                    for c in raw_chunks:
                        risk, sanitized, findings = indirect_injection_defense.inspect_chunk(c.content)
                        if risk > 0.0:
                            report["quarantined_instructions"] += 1
                        clean_chunk_texts.append(sanitized)
                        chunk_meta_list.append((c, sanitized, risk))

                    # Batch embed with Groq local deterministic vector engine
                    embeddings = await llm_gateway.embed(clean_chunk_texts)
                    bm25_batch = {}

                    for idx, (c, sanitized_text, risk) in enumerate(chunk_meta_list):
                        vec = embeddings[idx] if idx < len(embeddings) else []
                        db_chunk = DocumentChunk(
                            document_id=target_doc.id,
                            chunk_index=c.chunk_index,
                            content=sanitized_text,
                            token_count=c.token_estimate,
                            embedding_json=vec,
                            chunk_metadata=c.metadata,
                            injection_risk_score=risk,
                            is_active=True
                        )
                        db.add(db_chunk)
                        await db.flush()

                        vdoc = VectorDocument(
                            chunk_id=db_chunk.id,
                            document_id=target_doc.id,
                            content=sanitized_text,
                            embedding=vec,
                            metadata=c.metadata,
                            trust_level="trusted",
                            injection_risk_score=risk
                        )
                        vector_store.add_document(vdoc)
                        bm25_batch[db_chunk.id] = sanitized_text
                        report["total_chunks_indexed"] += 1

                    # Update BM25 index
                    current_bm25_docs = dict(bm25_retriever.documents)
                    current_bm25_docs.update(bm25_batch)
                    bm25_retriever.index_documents(current_bm25_docs)

                    await db.commit()

                    report["scanned_pages"].append({
                        "url": current_url,
                        "title": title,
                        "status": "updated" if is_update else "new",
                        "chunks": len(chunk_meta_list)
                    })

            # Step 4: Discover more links on this page if within max_depth
            if depth < self.max_depth and len(discovered_urls) < self.max_pages:
                try:
                    page_links = await self._extract_page_links(current_url, base_netloc)
                    for link in page_links:
                        norm_link = self.normalize_url(link)
                        if norm_link not in visited and norm_link not in discovered_urls:
                            if len(discovered_urls) >= self.max_pages:
                                break
                            discovered_urls.add(norm_link)
                            visited.add(norm_link)
                            queue.append((norm_link, depth + 1))
                except Exception as exc:
                    logger.debug(f"Could not extract links from {current_url}: {exc}")

        return report

    async def _extract_page_links(self, current_url: str, base_netloc: str) -> List[str]:
        """Extracts internal links from page HTML."""
        links = []
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            resp = await client.get(current_url)
            if resp.status_code == 200:
                soup = bs4.BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue
                    full_url = urljoin(current_url, href)
                    if full_url.endswith(IGNORED_EXTENSIONS):
                        continue
                    if self.is_same_domain(full_url, base_netloc):
                        links.append(full_url)
        return list(set(links))


website_crawler = WebsiteCrawler()
