from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag import (
    IndexStats,
    RAGSearchResponse,
    RAGStatus,
    RAGUnavailableError,
    rag_service,
)

router = APIRouter()


class RAGIndexRequest(BaseModel):
    """Body accepted by POST /api/rag/index and the POST /api/ingest alias."""

    force_reindex: bool = False


class RAGSearchRequest(BaseModel):
    query: str = Field(description="Natural-language search query")
    project_id: str = Field(
        default="", description="Restrict results to one project (optional)"
    )
    top_k: Optional[int] = Field(
        default=None, ge=1, le=50, description="Number of chunks to return"
    )


@router.get("/rag/status", response_model=RAGStatus)
def get_rag_status() -> RAGStatus:
    """Honest RAG/Qdrant status: healthy, unavailable, or empty index.

    Never claims connectivity: an unreachable store returns
    status=unavailable with a clear message.
    """
    return rag_service.get_status()


@router.post("/rag/index", response_model=IndexStats)
def index_documents(request: Optional[RAGIndexRequest] = None) -> IndexStats:
    """(Re)index all source documents into the vector store. Idempotent."""
    force = request.force_reindex if request else False
    try:
        return rag_service.index_all(force_reindex=force)
    except RAGUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/ingest", response_model=IndexStats, summary="Ingest demo data (alias)")
def ingest_demo_data(request: Optional[RAGIndexRequest] = None) -> IndexStats:
    """Alias for POST /api/rag/index (legacy frontend entry point)."""
    force = request.force_reindex if request else False
    try:
        return rag_service.index_all(force_reindex=force)
    except RAGUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/rag/search", response_model=RAGSearchResponse)
def search_documents(request: RAGSearchRequest) -> RAGSearchResponse:
    """Hybrid (vector + keyword + metadata) retrieval with explainable scores."""
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")
    filters = {"project_id": request.project_id} if request.project_id else None
    try:
        return rag_service.search_response(
            query, filters=filters, top_k=request.top_k
        )
    except RAGUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
