"""
Context Reranker and Diversity Filter with FlashRank Neural Cross-Encoder.
Filters out high-risk injection chunks, eliminates redundant duplicate texts,
and performs state-of-the-art cross-encoder neural reranking using FlashRank.
"""
from typing import List, Optional
from backend.app.retrieval.hybrid import RetrievedChunk
from backend.app.observability.logger import app_logger

try:
    from flashrank import Ranker, RerankRequest
    HAS_FLASHRANK = True
except ImportError:
    HAS_FLASHRANK = False


class ContextReranker:
    def __init__(self, model_name: str = "ms-marco-TinyBERT-L-2-v2"):
        self.ranker = None
        if HAS_FLASHRANK:
            try:
                self.ranker = Ranker(model_name=model_name)
                app_logger.info(f"Initialized FlashRank neural cross-encoder with model '{model_name}'.")
            except Exception as exc:
                app_logger.warning(f"Could not initialize FlashRank ({exc}). Falling back to heuristic RRF reranking.")

    def rerank_and_filter(
        self,
        chunks: List[RetrievedChunk],
        query: Optional[str] = None,
        top_n: int = 5,
        max_injection_risk: float = 0.4
    ) -> List[RetrievedChunk]:
        """
        Reranks chunks using FlashRank cross-encoder neural scoring,
        dropping high-risk injection chunks and deduplicating content.
        """
        filtered: List[RetrievedChunk] = []
        seen_texts = set()

        for chunk in chunks:
            # 1. Reject high-risk injection chunks
            if chunk.injection_risk_score > max_injection_risk:
                continue

            # 2. De-duplicate similar text snippets
            normalized_snippet = " ".join(chunk.content.split()[:25]).lower()
            if normalized_snippet in seen_texts:
                continue
            seen_texts.add(normalized_snippet)

            filtered.append(chunk)

        if not filtered:
            return []

        # 3. FlashRank Neural Cross-Encoder Reranking
        if self.ranker and query:
            try:
                passages = [
                    {"id": idx, "text": c.content, "meta": c.metadata}
                    for idx, c in enumerate(filtered)
                ]
                rerank_req = RerankRequest(query=query, passages=passages)
                results = self.ranker.rerank(rerank_req)

                reranked_chunks: List[RetrievedChunk] = []
                for res in results:
                    orig_chunk = filtered[res["id"]]
                    orig_chunk.score = float(res["score"])
                    reranked_chunks.append(orig_chunk)

                return reranked_chunks[:top_n]
            except Exception as exc:
                app_logger.warning(f"FlashRank reranking error ({exc}). Defaulting to RRF ordering.")

        # Fallback to initial score order
        return filtered[:top_n]


context_reranker = ContextReranker()
