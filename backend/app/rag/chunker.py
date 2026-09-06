"""
Heading-Aware and Paragraph-Aware Semantic Document Chunker.
Splits text intelligently along markdown headings and paragraphs while maintaining token overlaps.
"""
import re
from typing import Dict, List, Any


class Chunk:
    def __init__(self, content: str, chunk_index: int, metadata: Dict[str, Any], token_estimate: int):
        self.content = content
        self.chunk_index = chunk_index
        self.metadata = metadata
        self.token_estimate = token_estimate


class SemanticChunker:
    def __init__(self, target_chunk_size: int = 500, overlap_size: int = 75):
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size

    def estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / 3.8))

    def chunk_document(self, text: str, base_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Splits markdown text into semantic chunks preserving heading hierarchy and paragraph flow.
        """
        # Split by Markdown headings (# Heading 1, ## Heading 2, etc.)
        heading_sections = re.split(r"(?m)^(#{1,4}\s+.+)$", text)
        chunks: List[Chunk] = []
        chunk_idx = 0

        current_heading = base_metadata.get("title", "General")
        current_buffer: List[str] = []
        current_tokens = 0

        i = 0
        while i < len(heading_sections):
            part = heading_sections[i].strip()
            if not part:
                i += 1
                continue

            if part.startswith("#"):
                current_heading = part.lstrip("#").strip()
                i += 1
                continue

            # Split section by paragraphs
            paragraphs = re.split(r"\n\s*\n", part)
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                para_tokens = self.estimate_tokens(para)

                if current_tokens + para_tokens > self.target_chunk_size and current_buffer:
                    # Flush current chunk
                    chunk_text = "\n\n".join(current_buffer)
                    meta = dict(base_metadata)
                    meta["section_heading"] = current_heading

                    chunks.append(Chunk(
                        content=chunk_text,
                        chunk_index=chunk_idx,
                        metadata=meta,
                        token_estimate=current_tokens
                    ))
                    chunk_idx += 1

                    # Keep last paragraph for overlap if it fits
                    if current_tokens > self.overlap_size and len(current_buffer) > 1:
                        current_buffer = [current_buffer[-1], para]
                        current_tokens = self.estimate_tokens(current_buffer[0]) + para_tokens
                    else:
                        current_buffer = [para]
                        current_tokens = para_tokens
                else:
                    current_buffer.append(para)
                    current_tokens += para_tokens

            i += 1

        # Flush any remaining buffer
        if current_buffer:
            chunk_text = "\n\n".join(current_buffer)
            meta = dict(base_metadata)
            meta["section_heading"] = current_heading
            chunks.append(Chunk(
                content=chunk_text,
                chunk_index=chunk_idx,
                metadata=meta,
                token_estimate=current_tokens
            ))

        return chunks


semantic_chunker = SemanticChunker()
