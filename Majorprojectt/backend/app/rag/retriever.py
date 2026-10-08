"""Hybrid retrieval: vector similarity + keyword/text relevance + metadata.

The combination is intentionally simple and explainable - each chunk carries
a score_breakdown with the per-stage contributions:

    hybrid = 0.50 * vector + 0.35 * keyword + 0.15 * metadata

Supported filters (all optional): project_id, source_type, source
(github|gmail), repository, source_id, date_from/date_to (ISO timestamps,
applied after candidate retrieval).
"""

import time
from typing import Any, Dict, List, Optional

from app.rag.embeddings import EmbeddingProvider, get_embedding_provider, tokenize
from app.rag.models import RAGUnavailableError, RetrievalResult, RetrievedChunk
from app.rag.qdrant_client import VectorStore, get_vector_store
from app.rag.reranker import Reranker, normalize_query

VECTOR_WEIGHT = 0.50
KEYWORD_WEIGHT = 0.35
METADATA_WEIGHT = 0.15

# Relationship expansion: records linked to top candidates (issue <-> PR,
# thread <-> emails, cross-source links) are added as candidates with a
# decaying score. This is metadata/relationship relevance - explainable and
# deterministic.
EXPANSION_DECAY = 0.90
EXPANSION_PARENTS = 8

GITHUB_SOURCE_TYPES = [
    "github_repository",
    "github_issue",
    "github_pull_request",
    "github_commit",
    "github_review",
]
GMAIL_SOURCE_TYPES = ["gmail_thread", "gmail_email"]


def sibling_document_ids(payload: Dict[str, Any]) -> List[str]:
    """Document IDs of records explicitly linked to this payload's record."""
    data = payload.get("data") or {}
    source_type = str(payload.get("source_type") or "")
    doc_ids: List[str] = []

    def add(kind: str, ident: Any) -> None:
        if ident not in (None, "", 0, "0"):
            doc_ids.append(f"{kind}:{ident}")

    if source_type == "github_issue":
        add("github:pr", data.get("linked_pr_number"))
    elif source_type == "github_pull_request":
        add("github:issue", data.get("linked_issue_number"))
    elif source_type == "cross_source_link":
        blocker = data.get("primary_blocker") or {}
        add("github:issue", (blocker.get("github_issue") or {}).get("number"))
        add("github:pr", (blocker.get("github_pr") or {}).get("number"))
        add("gmail:thread", (blocker.get("gmail_thread") or {}).get("id"))
        add("github:pr", (data.get("github_pr") or {}).get("number"))
        add("gmail:thread", (data.get("gmail_thread") or {}).get("id"))
    return doc_ids


def prepare_store_filters(filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not filters:
        return None
    store_filters: Dict[str, Any] = {}
    for key in ("project_id", "source_type", "source_id", "repository"):
        value = filters.get(key)
        if value:
            store_filters[key] = value
    source = filters.get("source")
    if source:
        lowered = str(source).lower()
        if lowered == "github":
            store_filters["source_type"] = GITHUB_SOURCE_TYPES
        elif lowered == "gmail":
            store_filters["source_type"] = GMAIL_SOURCE_TYPES
    return store_filters or None


def apply_date_filters(
    chunks: List[RetrievedChunk], filters: Optional[Dict[str, Any]]
) -> List[RetrievedChunk]:
    date_from = str((filters or {}).get("date_from") or "")
    date_to = str((filters or {}).get("date_to") or "")
    if not date_from and not date_to:
        return chunks
    kept = []
    for chunk in chunks:
        timestamp = str(chunk.metadata.get("timestamp") or "")
        if date_from and timestamp and timestamp < date_from:
            continue
        if date_to and timestamp and timestamp > date_to:
            continue
        if (date_from or date_to) and not timestamp:
            continue
        kept.append(chunk)
    return kept


def _chunk_from_payload(
    payload: Dict[str, Any], score: float, breakdown: Dict[str, float]
) -> RetrievedChunk:
    metadata = {key: value for key, value in payload.items() if key != "content"}
    return RetrievedChunk(
        chunk_id=str(payload.get("chunk_id") or ""),
        document_id=str(payload.get("document_id") or ""),
        content=str(payload.get("content") or ""),
        score=round(score, 6),
        source_type=str(payload.get("source_type") or ""),
        source_id=str(payload.get("source_id") or ""),
        project_id=str(payload.get("project_id") or ""),
        title=str(payload.get("title") or ""),
        metadata=metadata,
        score_breakdown=breakdown,
    )


class HybridRetriever:
    """Vector + keyword + metadata retrieval with explainable scores."""

    def __init__(
        self,
        store: Optional[VectorStore] = None,
        embedder: Optional[EmbeddingProvider] = None,
        reranker: Optional[Reranker] = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.reranker = reranker or Reranker()

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> RetrievalResult:
        started = time.perf_counter()
        store = self.store or get_vector_store()
        embedder = self.embedder or get_embedding_provider()

        try:
            store.connect()
        except RAGUnavailableError:
            raise
        except Exception as exc:
            raise RAGUnavailableError(f"Vector store unavailable: {exc}") from exc

        store_filters = prepare_store_filters(filters)
        candidate_limit = max(top_k * 5, 25)

        # Stage 1: vector similarity -----------------------------------
        vector_raw: Dict[str, float] = {}
        vector_hits: List[tuple] = []
        try:
            vector_hits = store.search(
                embedder.embed_text(query), limit=candidate_limit, filters=store_filters
            )
        except RAGUnavailableError:
            raise
        except Exception:
            vector_hits = []  # keyword/metadata stages still work
        for raw_score, payload in vector_hits:
            chunk_id = str(payload.get("chunk_id") or "")
            if chunk_id:
                vector_raw[chunk_id] = float(raw_score)
        max_raw = max(vector_raw.values()) if vector_raw else 0.0
        vector_norm = {
            chunk_id: (max(0.0, value) / max_raw if max_raw > 0 else 0.0)
            for chunk_id, value in vector_raw.items()
        }

        # Stage 2: keyword/text relevance --------------------------------
        query_tokens = set(tokenize(query))
        query_normalized = normalize_query(query)
        keyword_scores: Dict[str, float] = {}
        payloads: List[Dict[str, Any]] = []
        try:
            payloads = store.scroll(filters=store_filters)
        except RAGUnavailableError:
            raise
        except Exception:
            payloads = []
        for payload in payloads:
            chunk_id = str(payload.get("chunk_id") or "")
            if not chunk_id:
                continue
            text = f"{payload.get('title', '')} {payload.get('content', '')}".lower()
            content_tokens = set(tokenize(text))
            overlap = (
                len(query_tokens & content_tokens) / len(query_tokens)
                if query_tokens
                else 0.0
            )
            phrase = 1.0 if query_normalized and query_normalized in text else 0.0
            keyword_scores[chunk_id] = min(1.0, 0.6 * overlap + 0.4 * phrase)

        # Stage 3: metadata relevance ------------------------------------
        payload_by_id: Dict[str, Dict[str, Any]] = {
            str(payload.get("chunk_id") or ""): payload
            for payload in payloads
            if payload.get("chunk_id")
        }
        for _, payload in vector_hits:
            chunk_id = str(payload.get("chunk_id") or "")
            if chunk_id and chunk_id not in payload_by_id:
                payload_by_id[chunk_id] = payload

        project_filter = (filters or {}).get("project_id", "")

        def metadata_score(payload: Dict[str, Any]) -> float:
            if project_filter:
                project_match = 1.0 if payload.get("project_id") == project_filter else 0.0
            else:
                project_match = 0.5 if payload.get("project_id") else 0.0
            title_tokens = set(tokenize(str(payload.get("title") or "")))
            title_overlap = (
                len(query_tokens & title_tokens) / len(query_tokens)
                if query_tokens
                else 0.0
            )
            return 0.6 * project_match + 0.4 * title_overlap

        # Combine ----------------------------------------------------------
        def combine(
            payload: Dict[str, Any],
            expansion_value: float = 0.0,
            expanded_from: str = "",
        ) -> RetrievedChunk:
            chunk_id = str(payload.get("chunk_id") or "")
            vector = vector_norm.get(chunk_id, 0.0)
            keyword = keyword_scores.get(chunk_id, 0.0)
            metadata = metadata_score(payload)
            hybrid = (
                VECTOR_WEIGHT * vector
                + KEYWORD_WEIGHT * keyword
                + METADATA_WEIGHT * metadata
            )
            if expansion_value > hybrid:
                hybrid = expansion_value
            breakdown = {
                "vector": round(vector, 6),
                "keyword": round(keyword, 6),
                "metadata": round(metadata, 6),
                "hybrid": round(hybrid, 6),
                "vector_raw": round(vector_raw.get(chunk_id, 0.0), 6),
            }
            if expansion_value > 0:
                breakdown["link_expansion"] = round(expansion_value, 6)
            chunk = _chunk_from_payload(payload, hybrid, breakdown)
            if expanded_from:
                chunk.metadata["expanded_from"] = expanded_from
            return chunk

        all_chunk_ids = set(vector_raw) | set(keyword_scores)
        by_id: Dict[str, RetrievedChunk] = {}
        for chunk_id in sorted(all_chunk_ids):
            payload = payload_by_id.get(chunk_id)
            if payload is None:
                continue
            by_id[chunk_id] = combine(payload)

        # Relationship expansion from the strongest candidates ----------------
        # Only explicit cross-record links (issue <-> PR, cross-source links)
        # expand; same-conversation records (thread <-> emails) are excluded
        # because they would flood the ranking with redundant siblings.
        doc_to_payloads: Dict[str, List[Dict[str, Any]]] = {}
        for payload in payload_by_id.values():
            doc_id = str(payload.get("document_id") or "")
            if doc_id:
                doc_to_payloads.setdefault(doc_id, []).append(payload)

        parents = sorted(
            by_id.values(), key=lambda c: (-c.score, c.chunk_id)
        )[:EXPANSION_PARENTS]
        for parent in parents:
            parent_payload = payload_by_id.get(parent.chunk_id) or {}
            expansion_value = parent.score * EXPANSION_DECAY
            for sibling_doc in sibling_document_ids(parent_payload):
                for sibling_payload in doc_to_payloads.get(sibling_doc, []):
                    sibling_id = str(sibling_payload.get("chunk_id") or "")
                    if not sibling_id or sibling_id == parent.chunk_id:
                        continue
                    existing = by_id.get(sibling_id)
                    if existing is None:
                        by_id[sibling_id] = combine(
                            sibling_payload,
                            expansion_value=expansion_value,
                            expanded_from=str(parent.source_id or ""),
                        )
                    else:
                        if expansion_value > existing.score:
                            existing.score = round(expansion_value, 6)
                            existing.score_breakdown["hybrid"] = existing.score
                        existing.score_breakdown["link_expansion"] = round(
                            expansion_value, 6
                        )
                        existing.metadata.setdefault(
                            "expanded_from", str(parent.source_id or "")
                        )

        candidates = apply_date_filters(list(by_id.values()), filters)
        candidates.sort(key=lambda c: (-c.score, c.chunk_id))
        vector_candidates = len(vector_raw)
        keyword_candidates = len(keyword_scores)
        candidates = candidates[:candidate_limit]

        # Rerank ------------------------------------------------------------
        ranked = self.reranker.rerank(query, candidates, filters=filters)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return RetrievalResult(
            query=query,
            top_k=top_k,
            chunks=ranked[:top_k],
            stats={
                "vector_candidates": vector_candidates,
                "keyword_candidates": keyword_candidates,
                "combined_candidates": len(candidates),
                "returned": min(len(ranked), top_k),
                "weights": {
                    "vector": VECTOR_WEIGHT,
                    "keyword": KEYWORD_WEIGHT,
                    "metadata": METADATA_WEIGHT,
                },
                "collection": store.collection,
                "mode": store.mode,
                "elapsed_ms": elapsed_ms,
            },
        )
