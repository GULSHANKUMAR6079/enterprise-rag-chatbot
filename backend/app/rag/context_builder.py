"""
Context Builder for RAG Pipeline.
Assembles verified knowledge chunks into structured prompt context with citation indices.
"""
from typing import Dict, List, Tuple
from backend.app.retrieval.hybrid import RetrievedChunk
from backend.app.schemas.chat import SourceCitation


class ContextBuilder:
    def __init__(self, max_context_tokens: int = 1500):
        self.max_context_tokens = max_context_tokens

    def estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / 3.8))

    def build_context(
        self,
        chunks: List[RetrievedChunk]
    ) -> Tuple[str, List[SourceCitation]]:
        """
        Builds XML-delimited trusted context section and citation mapping.
        """
        if not chunks:
            return "", []

        context_parts = []
        citations: List[SourceCitation] = []
        accumulated_tokens = 0

        for idx, chunk in enumerate(chunks, start=1):
            chunk_tokens = self.estimate_tokens(chunk.content)
            if accumulated_tokens + chunk_tokens > self.max_context_tokens:
                break

            doc_title = chunk.metadata.get("title", "Company Document")
            doc_url = chunk.metadata.get("source_url")
            doc_category = chunk.metadata.get("category", "Documentation")
            heading = chunk.metadata.get("section_heading", "")

            # Create citation object for API response
            citations.append(
                SourceCitation(
                    id=str(idx),
                    title=f"{doc_title}{': ' + heading if heading else ''}",
                    url=doc_url,
                    category=doc_category
                )
            )

            # Format chunk for LLM with explicit inert demarcation
            formatted_entry = (
                f"[{idx}] Source: {doc_title} | Category: {doc_category}\n"
                f"{chunk.content.strip()}"
            )
            context_parts.append(formatted_entry)
            accumulated_tokens += chunk_tokens

        joined_context = "\n\n".join(context_parts)
        xml_context = f"<trusted_context>\n{joined_context}\n</trusted_context>"
        return xml_context, citations


context_builder = ContextBuilder()
