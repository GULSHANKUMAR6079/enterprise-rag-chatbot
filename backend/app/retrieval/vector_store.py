"""
Vector Database Adapter.
Supports high-performance in-memory Cosine Similarity with NumPy and interfaces with pgvector.
"""
import numpy as np
from typing import Any, Dict, List, Optional, Tuple


class VectorDocument:
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        trust_level: str = "trusted",
        injection_risk_score: float = 0.0
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.embedding = np.array(embedding, dtype=np.float32)
        # Normalize vector for fast dot-product cosine similarity
        norm = np.linalg.norm(self.embedding)
        if norm > 0:
            self.embedding = self.embedding / norm
        self.metadata = metadata
        self.trust_level = trust_level
        self.injection_risk_score = injection_risk_score


class VectorStore:
    def __init__(self):
        self._documents: Dict[str, VectorDocument] = {}

    def add_document(self, doc: VectorDocument) -> None:
        self._documents[doc.chunk_id] = doc

    def count(self) -> int:
        return len(self._documents)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_similarity: float = 0.4,
        category_filter: Optional[str] = None
    ) -> List[Tuple[VectorDocument, float]]:
        """
        Executes Cosine Similarity search over all indexed chunks.
        """
        if not self._documents:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        results: List[Tuple[VectorDocument, float]] = []

        for doc in self._documents.values():
            if category_filter and doc.metadata.get("category") != category_filter:
                continue

            similarity = float(np.dot(q_vec, doc.embedding))
            if similarity >= min_similarity:
                results.append((doc, similarity))

        # Sort descending by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def clear(self) -> None:
        self._documents.clear()


vector_store = VectorStore()
