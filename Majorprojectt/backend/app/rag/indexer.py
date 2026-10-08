"""Idempotent indexing: documents -> chunks -> embeddings -> vector store.

Chunk IDs are deterministic ({document_id}:chunk:{n}) and point IDs are UUID5
of the chunk ID, so re-running the index replaces points instead of creating
duplicates. Document IDs are generated from actual source records - no
identifiers are hardcoded here.
"""

import time
from typing import List, Optional

from app.rag.chunker import DocumentChunker, chunker as default_chunker
from app.rag.document_loader import DocumentLoader, document_loader as default_loader
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.models import DocumentChunk, IndexStats, RAGError, RAGUnavailableError
from app.rag.qdrant_client import VectorStore, get_vector_store


def build_payload(chunk: DocumentChunk) -> dict:
    payload = dict(chunk.metadata)
    payload["content"] = chunk.content
    payload["chunk_id"] = chunk.chunk_id
    payload["document_id"] = chunk.document_id
    payload["chunk_index"] = chunk.chunk_index
    payload["total_chunks"] = chunk.total_chunks
    return payload


class Indexer:
    """Builds and upserts the index for all source documents."""

    def __init__(
        self,
        loader: Optional[DocumentLoader] = None,
        chunker: Optional[DocumentChunker] = None,
        embedder: Optional[EmbeddingProvider] = None,
        store: Optional[VectorStore] = None,
    ) -> None:
        self.loader = loader or default_loader
        self.chunker = chunker or default_chunker
        self.embedder = embedder or get_embedding_provider()
        self.store = store

    def run(self, force_reindex: bool = False) -> IndexStats:
        started = time.perf_counter()
        store = self.store or get_vector_store()
        documents_processed = 0
        chunks_created = 0
        chunks_indexed = 0
        skipped = 0
        errors = 0

        try:
            store.connect()
            store.ensure_collection(self.embedder.dim)
            if force_reindex:
                store.clear()
                store.ensure_collection(self.embedder.dim)
        except RAGUnavailableError:
            raise
        except Exception as exc:
            raise RAGUnavailableError(f"Cannot prepare vector store: {exc}") from exc

        documents = self.loader.load_documents()
        for document in documents:
            documents_processed += 1
            try:
                chunks = self.chunker.chunk(document)
                if not chunks:
                    skipped += 1
                    continue
                vectors = self.embedder.embed_texts([chunk.content for chunk in chunks])
                points = [
                    (chunk.chunk_id, vector, build_payload(chunk))
                    for chunk, vector in zip(chunks, vectors)
                ]
                indexed = store.upsert(points)
                chunks_created += len(chunks)
                chunks_indexed += indexed
            except Exception:
                errors += 1

        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        stats = IndexStats(
            documents_processed=documents_processed,
            chunks_created=chunks_created,
            chunks_indexed=chunks_indexed,
            skipped_records=skipped,
            errors=errors,
            duration_ms=duration_ms,
            detail=(
                f"indexed {chunks_indexed} chunks from {documents_processed} documents "
                f"into '{store.collection}' ({store.mode})"
            ),
        )
        return stats
