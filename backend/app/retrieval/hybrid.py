"""
Hybrid Retrieval with Reciprocal Rank Fusion (RRF).
Merges semantic vector embeddings with Okapi BM25 keyword search for robust retrieval.
"""
from typing import Any, Dict, List, Optional
from backend.app.core.config import settings
from backend.app.retrieval.bm25_retriever import bm25_retriever
from backend.app.retrieval.vector_store import VectorDocument, vector_store


class RetrievedChunk:
    def __init__(
        self,
        chunk_id: str,
        content: str,
        metadata: Dict[str, Any],
        score: float,
        source: str,
        trust_level: str = "trusted",
        injection_risk_score: float = 0.0
    ):
        self.chunk_id = chunk_id
        self.content = content
        self.metadata = metadata
        self.score = score
        self.source = source
        self.trust_level = trust_level
        self.injection_risk_score = injection_risk_score


class HybridRetriever:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        category_filter: Optional[str] = None
    ) -> List[RetrievedChunk]:
        """
        Executes hybrid search across dense vector space and sparse BM25 index.
        Fuses rankings using Reciprocal Rank Fusion (RRF).
        """
        # 1. Vector Search
        vector_matches = vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,
            min_similarity=settings.SIMILARITY_THRESHOLD,
            category_filter=category_filter
        )

        # 2. BM25 Search
        bm25_matches = bm25_retriever.search(query=query, top_k=top_k * 2)

        # 3. Reciprocal Rank Fusion
        rrf_scores: Dict[str, float] = {}
        chunk_lookup: Dict[str, RetrievedChunk] = {}

        # Process Vector Ranks
        for rank, (doc, sim_score) in enumerate(vector_matches, start=1):
            chunk_id = doc.chunk_id
            rrf_weight = 1.0 / (self.rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_weight

            if chunk_id not in chunk_lookup:
                chunk_lookup[chunk_id] = RetrievedChunk(
                    chunk_id=chunk_id,
                    content=doc.content,
                    metadata=doc.metadata,
                    score=sim_score,
                    source="vector",
                    trust_level=doc.trust_level,
                    injection_risk_score=doc.injection_risk_score
                )

        # Process BM25 Ranks
        for rank, (chunk_id, bm25_score) in enumerate(bm25_matches, start=1):
            rrf_weight = 1.0 / (self.rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + rrf_weight

            if chunk_id not in chunk_lookup and chunk_id in vector_store._documents:
                doc = vector_store._documents[chunk_id]
                chunk_lookup[chunk_id] = RetrievedChunk(
                    chunk_id=chunk_id,
                    content=doc.content,
                    metadata=doc.metadata,
                    score=bm25_score,
                    source="bm25",
                    trust_level=doc.trust_level,
                    injection_risk_score=doc.injection_risk_score
                )

        # Sort combined results by RRF score
        sorted_chunks = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        fused_results = []
        for chunk_id, fused_score in sorted_chunks[:top_k]:
            if chunk_id in chunk_lookup:
                c = chunk_lookup[chunk_id]
                c.score = fused_score
                fused_results.append(c)

        return fused_results


hybrid_retriever = HybridRetriever()
