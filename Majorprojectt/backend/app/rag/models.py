"""Internal Pydantic models for the RAG layer (Step 8).

Every model keeps enough metadata to trace a chunk back to its original
GitHub/Gmail/relationship source record.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RAGError(Exception):
    """Base error for the RAG layer."""


class RAGUnavailableError(RAGError):
    """Raised when the vector store (Qdrant) cannot be used."""


class RAGDocument(BaseModel):
    """A normalized document built from one synthetic source record."""

    document_id: str
    source_type: str  # github_issue, github_pr, ..., gmail_email, cross_source_link
    source_id: str  # e.g. "Issue #142", "PR #284", "GM-064"
    project_id: str = ""
    project: str = ""
    title: str = ""
    content: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """One chunk of a document, carrying source metadata for provenance."""

    chunk_id: str
    document_id: str
    content: str
    chunk_index: int = 0
    total_chunks: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """A chunk returned by retrieval, with explainable scoring."""

    chunk_id: str
    document_id: str = ""
    content: str = ""
    score: float = 0.0
    source_type: str = ""
    source_id: str = ""
    project_id: str = ""
    title: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    rerank_score: float = 0.0
    rerank_reasons: List[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    """Internal result of one hybrid retrieval pass."""

    query: str
    top_k: int = 10
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)


class RAGSearchResponse(BaseModel):
    """API-facing response for POST /api/rag/search."""

    query: str
    provider: str = ""
    collection: str = ""
    results: List[RetrievedChunk] = Field(default_factory=list)
    retrieval_statistics: Dict[str, Any] = Field(default_factory=dict)


class IndexStats(BaseModel):
    """Statistics returned by POST /api/rag/index."""

    documents_processed: int = 0
    chunks_created: int = 0
    chunks_indexed: int = 0
    skipped_records: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    detail: str = ""


class RAGStatus(BaseModel):
    """Honest status of the RAG/Qdrant layer for GET /api/rag/status."""

    status: str = "unavailable"  # healthy | unavailable
    provider: str = ""
    mode: str = ""  # embedded | server
    collection: str = ""
    embedding: str = ""
    documents: Optional[int] = None
    chunks: Optional[int] = None
    last_indexed: Optional[str] = None
    message: str = ""
