"""Main RAG interface: index_all / search / get_status / clear_index.

FastAPI-independent so it can be reused from agents, scripts and tests.
Honest status reporting: unavailable vector stores are reported as
unavailable with a clear message - never as connected.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.rag.indexer import Indexer
from app.rag.models import (
    IndexStats,
    RAGSearchResponse,
    RAGStatus,
    RAGUnavailableError,
    RetrievalResult,
    RetrievedChunk,
)
from app.rag.qdrant_client import VectorStore, get_vector_store
from app.rag.retriever import HybridRetriever


class RAGService:
    """Service facade over the RAG pipeline."""

    def __init__(
        self,
        store: Optional[VectorStore] = None,
        retriever: Optional[HybridRetriever] = None,
        indexer: Optional[Indexer] = None,
    ) -> None:
        self._store_override = store
        self._retriever = retriever
        self._indexer = indexer
        self.last_indexed: Optional[str] = None

    # ------------------------------------------------------------------ core

    def _store(self) -> VectorStore:
        return self._store_override or get_vector_store()

    def _get_indexer(self) -> Indexer:
        if self._indexer is None:
            self._indexer = Indexer(store=self._store_override)
        return self._indexer

    def _get_retriever(self) -> HybridRetriever:
        if self._retriever is None:
            self._retriever = HybridRetriever(store=self._store_override)
        return self._retriever

    # -------------------------------------------------------------- operations

    def index_all(self, force_reindex: bool = False) -> IndexStats:
        stats = self._get_indexer().run(force_reindex=force_reindex)
        self.last_indexed = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return stats

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> RetrievalResult:
        return self._get_retriever().search(
            query,
            filters=filters,
            top_k=top_k or settings.RAG_TOP_K,
        )

    def search_response(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> RAGSearchResponse:
        result = self.search(query, filters=filters, top_k=top_k)
        store = self._store()
        return RAGSearchResponse(
            query=result.query,
            provider=store.provider_name,
            collection=store.collection,
            results=result.chunks,
            retrieval_statistics=result.stats,
        )

    def get_status(self) -> RAGStatus:
        store = self._store()
        embedding = f"{settings.EMBEDDING_PROVIDER} · {settings.EMBEDDING_DIM}d"
        try:
            health = store.health()
        except Exception as exc:
            return RAGStatus(
                status="unavailable",
                provider=store.provider_name,
                mode=store.mode,
                collection=store.collection,
                embedding=embedding,
                message=f"Qdrant unavailable: {exc}",
            )
        if not health.ok:
            return RAGStatus(
                status="unavailable",
                provider=store.provider_name,
                mode=health.mode,
                collection=health.collection,
                embedding=embedding,
                message=health.message,
            )

        chunks: Optional[int] = None
        documents: Optional[int] = None
        try:
            chunks = store.count()
            payloads = store.scroll()
            documents = len({p.get("document_id") for p in payloads if p.get("document_id")})
        except Exception as exc:
            return RAGStatus(
                status="unavailable",
                provider=store.provider_name,
                mode=health.mode,
                collection=health.collection,
                embedding=embedding,
                message=f"Qdrant unavailable while reading counts: {exc}",
            )

        return RAGStatus(
            status="healthy",
            provider=store.provider_name,
            mode=health.mode,
            collection=health.collection,
            embedding=embedding,
            documents=documents,
            chunks=chunks,
            last_indexed=self.last_indexed,
            message=health.message,
        )

    def clear_index(self) -> None:
        store = self._store()
        store.clear()
        self.last_indexed = None


rag_service = RAGService()

__all__ = ["RAGService", "rag_service"]
