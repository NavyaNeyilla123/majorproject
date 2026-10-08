"""Deterministic, metadata-preserving chunking.

Strategy: split on paragraph boundaries, then sentence boundaries, then word
boundaries only when a unit still exceeds the maximum size. Units are packed
greedily so semantic meaning stays together. Short documents (typical for this
dataset) remain a single chunk.
"""

import re
from typing import List

from app.rag.models import DocumentChunk, RAGDocument

MAX_CHUNK_CHARS = 800

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WORD_BOUNDARY = re.compile(r"\s+")


def _split_units(text: str, max_chars: int) -> List[str]:
    units: List[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue
        for sentence in _SENTENCE_BOUNDARY.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= max_chars:
                units.append(sentence)
            else:
                # Last resort: hard split on word boundaries.
                current = ""
                for word in _WORD_BOUNDARY.split(sentence):
                    candidate = f"{current} {word}".strip()
                    if current and len(candidate) > max_chars:
                        units.append(current)
                        current = word
                    else:
                        current = candidate
                if current:
                    units.append(current)
    return units


def _pack_units(units: List[str], max_chars: int) -> List[str]:
    chunks: List[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= max_chars:
            current = f"{current} {unit}"
        else:
            chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


def split_content(content: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    content = (content or "").strip()
    if not content:
        return []
    if len(content) <= max_chars:
        return [content]
    return _pack_units(_split_units(content, max_chars), max_chars)


class DocumentChunker:
    """Chunks RAGDocuments while retaining document/source/project metadata."""

    def __init__(self, max_chars: int = MAX_CHUNK_CHARS) -> None:
        self.max_chars = max_chars

    def chunk(self, document: RAGDocument) -> List[DocumentChunk]:
        parts = split_content(document.content, self.max_chars)
        if not parts:
            return []
        total = len(parts)
        chunks: List[DocumentChunk] = []
        for index, part in enumerate(parts):
            metadata = dict(document.metadata)
            metadata.update(
                {
                    "document_id": document.document_id,
                    "chunk_id": f"{document.document_id}:chunk:{index}",
                    "chunk_index": index,
                    "total_chunks": total,
                    "source_type": document.source_type,
                    "source_id": document.source_id,
                    "project_id": document.project_id,
                    "project_name": document.project,
                    "title": document.title,
                    "timestamp": document.timestamp,
                }
            )
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.document_id}:chunk:{index}",
                    document_id=document.document_id,
                    content=part,
                    chunk_index=index,
                    total_chunks=total,
                    metadata=metadata,
                )
            )
        return chunks


chunker = DocumentChunker()

__all__ = ["DocumentChunker", "chunker", "split_content", "MAX_CHUNK_CHARS"]
