"""Step 8 tests: document pipeline, hybrid retrieval, RAG endpoints,
and RetrievalAgent RAG integration.

Identifiers like 142/284/GM-064 are hardcoded here only - the
implementation must never special-case them.
"""

import math
import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agents.models import AgentContext
from app.agents.retrieval_agent import RetrievalAgent
from app.core.config import settings
from app.rag import (
    DocumentChunker,
    DocumentLoader,
    LocalHashEmbeddingProvider,
    Reranker,
    RAGUnavailableError,
    rag_service,
)
from app.rag.qdrant_client import (
    InMemoryVectorStore,
    StoreHealth,
    set_vector_store,
)

client = TestClient(app)

CRITICAL_QUERIES = [
    "security approval Platform API v2.4",
    "What could delay the Platform API v2.4 release?",
    "Is Platform API v2.4 ready for release?",
]
CRITICAL_SOURCE_IDS = ["Issue #142", "PR #284", "GM-064"]
PROJECT_ID = "proj-platform-api"
TOTAL_DOCUMENTS = 160


class BrokenStore(InMemoryVectorStore):
    """Store that behaves like an unreachable Qdrant server."""

    mode = "server"

    def connect(self) -> None:
        raise RAGUnavailableError(
            "Qdrant unavailable (server mode, url=http://localhost:6333): "
            "connection refused"
        )

    def health(self) -> StoreHealth:
        return StoreHealth(
            ok=False,
            message="Qdrant unavailable: connection refused",
            mode="server",
            collection=self.collection,
        )

    def ensure_collection(self, dim: int) -> None:
        raise RAGUnavailableError("Vector store unavailable: connection refused")

    def search(self, vector, limit, filters=None):
        raise RAGUnavailableError("Vector store unavailable: connection refused")

    def scroll(self, filters=None):
        raise RAGUnavailableError("Vector store unavailable: connection refused")

    def count(self) -> int:
        raise RAGUnavailableError("Vector store unavailable: connection refused")


@pytest.fixture(scope="module")
def indexed_rag():
    """Swap in a fresh in-memory store and index the dataset once."""
    previous = get_vector_store_safe()
    store = InMemoryVectorStore()
    set_vector_store(store)
    rag_service.last_indexed = None
    rag_service.index_all(force_reindex=True)
    yield store
    set_vector_store(previous)
    rag_service.last_indexed = None


@pytest.fixture()
def empty_rag():
    previous = get_vector_store_safe()
    store = InMemoryVectorStore()
    set_vector_store(store)
    rag_service.last_indexed = None
    yield store
    set_vector_store(previous)
    rag_service.last_indexed = None


@pytest.fixture()
def broken_rag():
    previous = get_vector_store_safe()
    store = BrokenStore()
    set_vector_store(store)
    rag_service.last_indexed = None
    yield store
    set_vector_store(previous)
    rag_service.last_indexed = None


def get_vector_store_safe():
    from app.rag.qdrant_client import get_vector_store

    return get_vector_store()


def make_context(run_id: str = "KO-RAGT1") -> AgentContext:
    return AgentContext(
        run_id=run_id,
        question=CRITICAL_QUERIES[0],
        project_id=PROJECT_ID,
        retrieval_objectives=["release readiness", "approval status"],
    )


# ------------------------------------------------- 1. document loading

def test_document_loader_builds_all_source_documents():
    docs = DocumentLoader().load_documents()
    assert len(docs) == TOTAL_DOCUMENTS
    ids = {d.document_id for d in docs}
    assert "github:issue:142" in ids
    assert "github:pr:284" in ids
    assert "gmail:thread:GM-064" in ids
    source_types = {d.source_type for d in docs}
    assert {
        "github_repository",
        "github_issue",
        "github_pull_request",
        "github_commit",
        "github_review",
        "gmail_thread",
        "gmail_email",
        "cross_source_link",
    } <= source_types
    # dataset loaded in place, not copied
    assert not (backend_root / "data" / ".copied").exists()


def test_document_loader_preserves_provenance_metadata():
    docs = DocumentLoader().load_documents()
    issue = next(d for d in docs if d.document_id == "github:issue:142")
    assert issue.source_id == "Issue #142"
    assert issue.project_id == "proj-platform-api"
    assert issue.metadata["project_id"] == "proj-platform-api"
    assert issue.metadata["timestamp"]
    assert isinstance(issue.metadata["relationships"], dict)
    assert issue.metadata["data"].get("number") == 142
    thread = next(d for d in docs if d.document_id == "gmail:thread:GM-064")
    assert thread.metadata["project_id"] == PROJECT_ID


# ---------------------------------------------------------- 2. chunking

def test_chunker_is_deterministic_and_preserves_metadata():
    docs = DocumentLoader().load_documents()
    chunker = DocumentChunker()
    doc = next(d for d in docs if d.document_id == "github:pr:284")
    first = chunker.chunk(doc)
    second = chunker.chunk(doc)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.content for c in first] == [c.content for c in second]
    assert first, "document must produce at least one chunk"
    for chunk in first:
        assert chunk.metadata["source_id"] == doc.source_id
        assert chunk.metadata["project_id"] == doc.project_id
        assert chunk.content.strip()
    # all documents chunk without errors
    total = sum(len(chunker.chunk(d)) for d in docs)
    assert total >= TOTAL_DOCUMENTS


# ------------------------------------------------------ 3. embeddings

def test_local_hash_embeddings_are_deterministic_and_normalized():
    provider = LocalHashEmbeddingProvider()
    assert provider.provider_name == "local-hash"
    assert provider.dim == 1536
    first = provider.embed_text("security approval Platform API")
    second = provider.embed_text("security approval Platform API")
    assert first == second
    assert len(first) == 1536
    assert any(value != 0.0 for value in first)
    norm = math.sqrt(sum(v * v for v in first))
    assert abs(norm - 1.0) < 1e-6
    other = provider.embed_text("unrelated gardening topics entirely")
    assert first != other
    batch = provider.embed_texts(["alpha beta", "gamma delta"])
    assert len(batch) == 2
    assert batch[0] == provider.embed_text("alpha beta")


# -------------------------------------------------------- 4. indexing

def test_indexing_uses_configured_collection_and_covers_dataset(indexed_rag):
    assert settings.QDRANT_COLLECTION == "knowledgeops_projects"
    stats = rag_service.index_all()
    assert stats.documents_processed == TOTAL_DOCUMENTS
    assert stats.chunks_created == TOTAL_DOCUMENTS
    assert stats.errors == 0
    assert indexed_rag.count() == TOTAL_DOCUMENTS
    assert "knowledgeops_projects" in stats.detail


def test_indexing_is_idempotent(indexed_rag):
    first = rag_service.index_all(force_reindex=True)
    count_after_first = indexed_rag.count()
    second = rag_service.index_all(force_reindex=False)
    count_after_second = indexed_rag.count()
    assert second.documents_processed == first.documents_processed
    assert second.chunks_created == first.chunks_created
    assert count_after_second == count_after_first == TOTAL_DOCUMENTS


# -------------------------------------------- 5-8. hybrid search core

def test_hybrid_search_returns_explainable_score_breakdown(indexed_rag):
    result = rag_service.search(CRITICAL_QUERIES[0], top_k=10)
    assert result.chunks, "expected ranked chunks"
    for chunk in result.chunks:
        breakdown = chunk.score_breakdown
        for key in ("vector", "keyword", "metadata", "hybrid"):
            assert key in breakdown, f"missing {key} in score breakdown"
            assert 0.0 <= breakdown[key] <= 1.5
        assert chunk.rerank_reasons
        assert chunk.rerank_score >= 0.0
    hybrid_values = [c.score_breakdown["hybrid"] for c in result.chunks]
    assert all(0.0 <= value <= 1.5 for value in hybrid_values)
    rerank_values = [c.rerank_score for c in result.chunks]
    assert rerank_values == sorted(rerank_values, reverse=True)


def test_search_filters_by_project(indexed_rag):
    filtered = rag_service.search(CRITICAL_QUERIES[0], filters={"project_id": PROJECT_ID})
    assert filtered.chunks
    for chunk in filtered.chunks:
        assert chunk.project_id == PROJECT_ID
    unfiltered = rag_service.search(CRITICAL_QUERIES[0], top_k=30)
    other_projects = {c.project_id for c in unfiltered.chunks} - {PROJECT_ID}
    assert other_projects, "unfiltered search should reach other projects"


def test_reranker_is_deterministic(indexed_rag):
    first = rag_service.search(CRITICAL_QUERIES[1], top_k=10)
    second = rag_service.search(CRITICAL_QUERIES[1], top_k=10)
    first_ranking = [(c.source_id, c.rerank_score) for c in first.chunks]
    second_ranking = [(c.source_id, c.rerank_score) for c in second.chunks]
    assert first_ranking == second_ranking
    # rerank is a pure function of the chunk (no randomness, no LLM)
    reranker = Reranker()
    chunk = first.chunks[0]
    reranked = reranker.rerank(
        CRITICAL_QUERIES[1], [chunk.model_copy(deep=True)]
    )[0]
    assert reranked.rerank_score == chunk.rerank_score
    assert reranked.rerank_reasons == chunk.rerank_reasons


def test_retrieved_chunks_carry_full_provenance(indexed_rag):
    result = rag_service.search(CRITICAL_QUERIES[0], top_k=10)
    for chunk in result.chunks:
        assert chunk.source_type
        assert chunk.source_id
        assert chunk.project_id == PROJECT_ID
        assert chunk.title
        assert chunk.metadata.get("timestamp") or chunk.source_type == "relationship"
        assert isinstance(chunk.metadata.get("relationships"), dict)
        assert chunk.document_id
        assert chunk.chunk_id.startswith(chunk.document_id)


# ------------------------------------- 9. critical retrieval scenario

@pytest.mark.parametrize("query", CRITICAL_QUERIES)
def test_critical_queries_retrieve_all_three_records(indexed_rag, query):
    result = rag_service.search(
        query, filters={"project_id": PROJECT_ID}, top_k=10
    )
    ids = [c.source_id for c in result.chunks]
    for target in CRITICAL_SOURCE_IDS:
        assert target in ids, f"'{target}' missing from top-10 for query: {query} -> {ids}"


# ------------------------------------------------------ 10. status API

def test_rag_status_endpoint_reports_healthy_index(indexed_rag):
    rag_service.index_all()
    response = client.get("/api/rag/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["collection"] == "knowledgeops_projects"
    assert body["documents"] == TOTAL_DOCUMENTS
    assert body["chunks"] == TOTAL_DOCUMENTS
    assert body["last_indexed"]
    assert "local-hash" in body["embedding"]
    assert body["mode"] in ("memory", "embedded", "server")


def test_rag_status_on_empty_index_is_honest(empty_rag):
    response = client.get("/api/rag/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["documents"] == 0
    assert body["chunks"] == 0
    assert body["last_indexed"] is None


def test_rag_status_reports_unavailable_honestly(broken_rag):
    response = client.get("/api/rag/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert "connection refused" in body["message"]
    assert body["status"] != "connected"


# ------------------------------------------------- 11. index API

def test_index_endpoint_is_idempotent(indexed_rag):
    first = client.post("/api/rag/index", json={"force_reindex": True})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["documents_processed"] == TOTAL_DOCUMENTS
    assert first_body["chunks_indexed"] == TOTAL_DOCUMENTS
    assert first_body["errors"] == 0

    second = client.post("/api/rag/index", json={"force_reindex": False})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["documents_processed"] == first_body["documents_processed"]
    assert second_body["chunks_indexed"] == first_body["chunks_indexed"]
    assert indexed_rag.count() == TOTAL_DOCUMENTS


def test_ingest_alias_indexes_documents(indexed_rag):
    response = client.post("/api/ingest", json={"force_reindex": False})
    assert response.status_code == 200
    body = response.json()
    assert body["documents_processed"] == TOTAL_DOCUMENTS
    assert body["chunks_created"] == TOTAL_DOCUMENTS


def test_index_endpoint_returns_503_when_store_unavailable(broken_rag):
    response = client.post("/api/rag/index", json={"force_reindex": False})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


# -------------------------------------------------- 12. search API

def test_search_endpoint_returns_ranked_explained_results(indexed_rag):
    response = client.post(
        "/api/rag/search",
        json={
            "query": CRITICAL_QUERIES[2],
            "project_id": PROJECT_ID,
            "top_k": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == CRITICAL_QUERIES[2]
    assert body["collection"] == "knowledgeops_projects"
    assert body["results"]
    rerank_scores = [r["rerank_score"] for r in body["results"]]
    assert rerank_scores == sorted(rerank_scores, reverse=True)
    for result in body["results"]:
        assert "hybrid" in result["score_breakdown"]
        assert result["source_id"]
        assert result["rerank_reasons"]


def test_search_endpoint_rejects_empty_query(indexed_rag):
    response = client.post("/api/rag/search", json={"query": "   "})
    assert response.status_code == 400


def test_search_endpoint_returns_503_when_store_unavailable(broken_rag):
    response = client.post("/api/rag/search", json={"query": CRITICAL_QUERIES[0]})
    assert response.status_code == 503


# --------------------------------- 13. RetrievalAgent RAG integration

def test_retrieval_agent_merges_rag_chunks_after_mcp_selection(indexed_rag):
    # Baseline: MCP selection with an empty RAG index
    set_vector_store(InMemoryVectorStore())
    base_agent = RetrievalAgent()
    base_ctx = make_context(run_id="KO-RAGT1")
    base_agent.execute(base_ctx)
    baseline_ids = [r.source_id for r in base_ctx.retrieved_records]
    assert "Issue #142" in baseline_ids
    assert "empty index" in base_agent.detail

    # Merged: same query with the indexed store active
    set_vector_store(indexed_rag)
    agent = RetrievalAgent()
    ctx = make_context(run_id="KO-RAGT2")
    agent.execute(ctx)
    merged = ctx.retrieved_records
    merged_ids = [r.source_id for r in merged]

    # MCP selection runs first and is untouched, RAG records are appended
    assert merged_ids[: len(baseline_ids)] == baseline_ids
    assert len(merged_ids) == len(set(merged_ids)), "duplicate source_id in merge"
    assert "rag" in agent.detail

    extras = merged[len(baseline_ids):]
    assert extras, "expected RAG-only records appended"
    for record in extras:
        assert "rag_chunk" in record.relationships
        assert "rag_score" in record.relationships
        assert record.project_id == PROJECT_ID

    for target in CRITICAL_SOURCE_IDS:
        assert target in merged_ids


def test_retrieval_agent_degrades_to_mcp_only_when_index_empty(empty_rag):
    agent = RetrievalAgent()
    ctx = make_context(run_id="KO-RAGT3")
    agent.execute(ctx)
    ids = [r.source_id for r in ctx.retrieved_records]
    assert ids, "MCP selection must still return records"
    assert "Issue #142" in ids
    assert "empty index" in agent.detail
    assert "mcp-only" in agent.detail


def test_retrieval_agent_degrades_to_mcp_only_when_store_unavailable(broken_rag):
    agent = RetrievalAgent()
    ctx = make_context(run_id="KO-RAGT4")
    agent.execute(ctx)
    ids = [r.source_id for r in ctx.retrieved_records]
    assert ids, "MCP selection must still return records"
    assert "Issue #142" in ids
    assert "rag unavailable" in agent.detail
    assert "mcp-only" in agent.detail
