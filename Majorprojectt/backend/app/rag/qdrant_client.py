"""Vector store abstraction over Qdrant.

Modes (configured via settings / environment):
- ``server``:   QDRANT_URL set -> connect to a real Qdrant server.
- ``embedded``: QDRANT_URL empty -> qdrant-client embedded mode with
                persistent local storage (QDRANT_PATH). Qdrant runs in-process.
- ``memory``:   InMemoryVectorStore for tests (same interface).

Collection name comes from QDRANT_COLLECTION (default: knowledgeops_projects).
Health reporting is always honest - unreachable servers are reported as
unavailable with a clear message, never as connected.
"""

import math
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.rag.models import RAGUnavailableError

POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "knowledgeops-rag-chunk")


class StoreHealth:
    def __init__(self, ok: bool, message: str, mode: str, collection: str) -> None:
        self.ok = ok
        self.message = message
        self.mode = mode
        self.collection = collection


def point_id_for(chunk_id: str) -> str:
    """Deterministic UUID5 from the chunk identity (idempotent upserts)."""
    return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)


def matches_filters(payload: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """Equality ('any' for lists) matching used by the in-memory store."""
    if not filters:
        return True
    for key, expected in filters.items():
        actual = payload.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif str(actual) != str(expected):
            return False
    return True


def active_collection() -> str:
    """Collection for the active MCP provider mode.

    Mock mode (default) keeps using QDRANT_COLLECTION (the synthetic index).
    Real mode uses RAG_REAL_COLLECTION so real ingestion, reindexing and
    clear operations can never touch the synthetic collection.
    """
    try:
        from app.mcp.provider import resolve_provider_name

        if resolve_provider_name() == "real":
            return settings.RAG_REAL_COLLECTION
    except Exception:  # provider resolution must never break the store
        pass
    return settings.QDRANT_COLLECTION


class VectorStore(ABC):
    """Common operations: connect, collection lifecycle, upsert, search, health."""

    provider_name: str = "abstract"
    mode: str = "abstract"

    def __init__(self, collection: str = None) -> None:
        self.collection = collection or active_collection()

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> StoreHealth:
        raise NotImplementedError

    @abstractmethod
    def ensure_collection(self, dim: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def has_collection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, points: List[Tuple[str, List[float], Dict[str, Any]]]) -> int:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        raise NotImplementedError

    @abstractmethod
    def scroll(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError


class QdrantVectorStore(VectorStore):
    """Qdrant integration (server mode when QDRANT_URL is set, else embedded)."""

    provider_name = "qdrant"

    def __init__(self, collection: str = None) -> None:
        super().__init__(collection)
        self._client = None
        self._url = settings.QDRANT_URL
        self._api_key = settings.QDRANT_API_KEY
        self._path = settings.QDRANT_PATH
        self.mode = "server" if self._url else "embedded"

    def connect(self) -> None:
        if self._client is not None:
            return
        from qdrant_client import QdrantClient  # imported lazily (heavy module)

        try:
            if self._url:
                client = QdrantClient(url=self._url, api_key=self._api_key or None, timeout=10)
                client.get_collections()  # verifies connectivity
            else:
                client = QdrantClient(path=self._path)
        except Exception as exc:
            raise RAGUnavailableError(
                f"Qdrant unavailable ({self.mode} mode"
                + (f", url={self._url}" if self._url else f", path={self._path}")
                + f"): {exc}"
            ) from exc
        self._client = client

    def _require_client(self):
        try:
            self.connect()
        except RAGUnavailableError:
            raise
        return self._client

    def health(self) -> StoreHealth:
        try:
            client = self._require_client()
            client.get_collections()
        except Exception as exc:
            return StoreHealth(
                ok=False,
                message=f"Qdrant unavailable: {exc}",
                mode=self.mode,
                collection=self.collection,
            )
        exists = self.has_collection()
        message = (
            f"Qdrant reachable ({self.mode}); collection '{self.collection}' "
            + ("exists" if exists else "not created yet")
        )
        return StoreHealth(ok=True, message=message, mode=self.mode, collection=self.collection)

    def has_collection(self) -> bool:
        client = self._require_client()
        return bool(client.collection_exists(self.collection))

    def ensure_collection(self, dim: int) -> None:
        from qdrant_client import models

        client = self._require_client()
        if not client.collection_exists(self.collection):
            client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )

    def upsert(self, points: List[Tuple[str, List[float], Dict[str, Any]]]) -> int:
        from qdrant_client import models

        client = self._require_client()
        if not points:
            return 0
        batch = [
            models.PointStruct(id=point_id_for(chunk_id), vector=vector, payload=payload)
            for chunk_id, vector, payload in points
        ]
        client.upsert(collection_name=self.collection, points=batch)
        return len(batch)

    def _build_filter(self, filters: Optional[Dict[str, Any]]):
        if not filters:
            return None
        from qdrant_client import models

        conditions = []
        for key, expected in filters.items():
            if isinstance(expected, list):
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchAny(any=expected))
                )
            else:
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=expected))
                )
        return models.Filter(must=conditions)

    def search(
        self,
        vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        client = self._require_client()
        if not self.has_collection():
            return []
        response = client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=self._build_filter(filters),
            limit=limit,
            with_payload=True,
        )
        return [(point.score, dict(point.payload or {})) for point in response.points]

    def scroll(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        client = self._require_client()
        if not self.has_collection():
            return []
        payloads: List[Dict[str, Any]] = []
        next_offset = None
        while True:
            points, next_offset = client.scroll(
                collection_name=self.collection,
                limit=256,
                offset=next_offset,
                scroll_filter=self._build_filter(filters),
                with_payload=True,
            )
            payloads.extend(dict(point.payload or {}) for point in points)
            if next_offset is None:
                break
        return payloads

    def count(self) -> int:
        client = self._require_client()
        if not self.has_collection():
            return 0
        return int(client.count(self.collection).count)

    def clear(self) -> None:
        client = self._require_client()
        if client.collection_exists(self.collection):
            client.delete_collection(self.collection)


class InMemoryVectorStore(VectorStore):
    """Pure-Python vector store with the same semantics (tests / injection)."""

    provider_name = "in-memory"
    mode = "memory"

    def __init__(self, collection: str = None) -> None:
        super().__init__(collection)
        self._points: Dict[str, Tuple[List[float], Dict[str, Any]]] = {}
        self._dim = 0

    def connect(self) -> None:
        return

    def health(self) -> StoreHealth:
        return StoreHealth(
            ok=True,
            message=f"in-memory store ready; collection '{self.collection}' "
            f"holds {len(self._points)} points",
            mode=self.mode,
            collection=self.collection,
        )

    def ensure_collection(self, dim: int) -> None:
        self._dim = dim

    def has_collection(self) -> bool:
        return True

    def upsert(self, points: List[Tuple[str, List[float], Dict[str, Any]]]) -> int:
        for chunk_id, vector, payload in points:
            self._points[point_id_for(chunk_id)] = (vector, dict(payload))
        return len(points)

    def search(
        self,
        vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        scored = []
        for _, (stored_vector, payload) in self._points.items():
            if not matches_filters(payload, filters):
                continue
            scored.append((cosine_similarity(vector, stored_vector), dict(payload)))
        scored.sort(key=lambda item: (-item[0], str(item[1].get("chunk_id", ""))))
        return scored[:limit]

    def scroll(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        payloads = [
            dict(payload)
            for _, payload in self._points.values()
            if matches_filters(payload, filters)
        ]
        payloads.sort(key=lambda payload: str(payload.get("chunk_id", "")))
        return payloads

    def count(self) -> int:
        return len(self._points)

    def clear(self) -> None:
        self._points.clear()


_vector_store: Optional[VectorStore] = None
_vector_store_pinned = False


def get_vector_store() -> VectorStore:
    """Process-wide vector store singleton (server or embedded Qdrant).

    Re-resolves the collection when the active MCP provider mode changes, so
    switching MCP_PROVIDER between mock and real points at the right
    collection. Stores injected via set_vector_store are never replaced.
    """
    global _vector_store, _vector_store_pinned
    desired = active_collection()
    if _vector_store is None or (not _vector_store_pinned and _vector_store.collection != desired):
        store = QdrantVectorStore(collection=desired)
        store.connect()
        _vector_store = store
    return _vector_store


def set_vector_store(store: Optional[VectorStore]) -> None:
    """Replace the process-wide store (dependency injection for tests)."""
    global _vector_store, _vector_store_pinned
    _vector_store = store
    _vector_store_pinned = store is not None
