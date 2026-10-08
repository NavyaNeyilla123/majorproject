"""Loads source records through the MCP provider seam and normalizes them
into RAGDocuments.

The synthetic dataset is NOT copied anywhere: records are fetched from the
active MCPProvider (MockMCPProvider by default) and turned into documents
in memory, then embedded/indexed by the indexer.
"""

from typing import List, Optional

from app.mcp import MCPProvider, MCPRecord, get_mcp_provider
from app.rag.models import RAGDocument

CANDIDATE_LIMIT = 1000

SOURCE_TYPE_BY_RECORD_TYPE = {
    "repository": "github_repository",
    "issue": "github_issue",
    "pull_request": "github_pull_request",
    "commit": "github_commit",
    "review": "github_review",
    "thread": "gmail_thread",
    "email": "gmail_email",
    "cross_source_link": "cross_source_link",
}


def _join(*parts: object) -> str:
    return " ".join(str(p) for p in parts if p not in (None, "", []))


def _labels(data: dict) -> str:
    labels = data.get("labels") or []
    return ", ".join(str(label) for label in labels)


def build_content(record: MCPRecord) -> str:
    """Meaningful searchable text assembled from real fields only."""
    data = record.data
    source_type = SOURCE_TYPE_BY_RECORD_TYPE.get(record.record_type, record.record_type)

    if source_type == "github_issue":
        return _join(
            data.get("title"), data.get("body"),
            f"labels: {_labels(data)}" if _labels(data) else "",
            f"status: {data.get('status')}", f"severity: {data.get('severity')}",
            data.get("repository"), data.get("project_name"),
            f"author: {data.get('author')}",
        )
    if source_type == "github_pull_request":
        return _join(
            data.get("title"), data.get("summary"),
            f"status: {data.get('status')}", f"ci: {data.get('ci_status')}",
            data.get("next_step"),
            f"reviewers: {', '.join(data.get('reviewers') or [])}"
            if data.get("reviewers") else "",
            data.get("repository"), data.get("project_name"),
            f"author: {data.get('author')}",
        )
    if source_type == "github_commit":
        return _join(data.get("message"), data.get("author"), data.get("repository"))
    if source_type == "github_review":
        return _join(
            data.get("state"), data.get("body"),
            f"reviewer: {data.get('reviewer')}", data.get("repository"),
        )
    if source_type == "github_repository":
        return _join(
            data.get("name"), data.get("org"), data.get("project_name"),
            f"health: {data.get('health_status')}",
        )
    if source_type == "gmail_thread":
        return _join(
            data.get("subject"), data.get("snippet"),
            f"category: {data.get('category')}", data.get("project_name"),
            f"participants: {', '.join(data.get('participants') or [])}"
            if data.get("participants") else "",
        )
    if source_type == "gmail_email":
        return _join(
            data.get("subject"), data.get("body"),
            data.get("sender"),
            f"recipients: {', '.join(data.get('recipients') or [])}"
            if data.get("recipients") else "",
            data.get("project_name"),
        )
    if source_type == "cross_source_link":
        facts = data.get("provenance_facts") or []
        return _join(
            data.get("description"),
            "; ".join(str(f) for f in facts),
            f"target release: {data.get('target_release')}",
            f"target date: {data.get('target_date')}",
            data.get("project_name"),
        )
    return _join(record.source_id, str(data))


def build_title(record: MCPRecord) -> str:
    data = record.data
    return str(
        data.get("title")
        or data.get("subject")
        or data.get("name")
        or data.get("description")
        or record.source_id
    )


def build_timestamp(record: MCPRecord) -> str:
    data = record.data
    return str(
        data.get("updated_at")
        or data.get("created_at")
        or data.get("last_message_at")
        or data.get("received_at")
        or data.get("timestamp")
        or data.get("submitted_at")
        or data.get("synced_at")
        or ""
    )


def build_document_id(record: MCPRecord, source_type: str) -> str:
    """Deterministic document identity generated from the source record.

    Records normalized from a real MCP server are prefixed with "real:" so a
    real record can never collide with a synthetic record that shares a
    number (for example a real Issue #142 vs the synthetic Issue #142).
    Synthetic (mock) IDs are unchanged, so the existing index stays valid.
    """
    data = record.data
    if source_type == "github_issue":
        document_id = f"github:issue:{data.get('number')}"
    elif source_type == "github_pull_request":
        document_id = f"github:pr:{data.get('number')}"
    elif source_type == "github_commit":
        document_id = f"github:commit:{data.get('sha')}"
    elif source_type == "github_review":
        document_id = f"github:review:{data.get('id')}"
    elif source_type == "github_repository":
        document_id = f"github:repo:{data.get('id')}"
    elif source_type == "gmail_thread":
        document_id = f"gmail:thread:{data.get('id')}"
    elif source_type == "gmail_email":
        document_id = f"gmail:email:{data.get('id')}"
    elif source_type == "cross_source_link":
        document_id = f"relationship:{data.get('id')}"
    else:
        document_id = f"{source_type}:{record.source_id}"
    if record.source_mode == "real":
        return f"real:{document_id}"
    return document_id


def to_rag_document(record: MCPRecord) -> Optional[RAGDocument]:
    source_type = SOURCE_TYPE_BY_RECORD_TYPE.get(record.record_type)
    if not source_type:
        return None
    data = record.data
    document_id = build_document_id(record, source_type)
    if source_type == "gmail_thread":
        thread_ref = str(data.get("id") or "")
    else:
        thread_ref = str(data.get("thread_id") or "")
    return RAGDocument(
        document_id=document_id,
        source_type=source_type,
        source_id=record.source_id,
        project_id=record.project_id,
        project=str(data.get("project_name") or ""),
        title=build_title(record),
        content=build_content(record),
        timestamp=build_timestamp(record),
        metadata={
            "source_type": source_type,
            "source_id": record.source_id,
            "source_mode": record.source_mode,
            "project_id": record.project_id,
            "project_name": data.get("project_name") or "",
            "title": build_title(record),
            "timestamp": build_timestamp(record),
            "repository": data.get("repository") or "",
            "thread_id": thread_ref,
            "data": dict(data),
            "relationships": dict(record.relationships),
        },
    )


class DocumentLoader:
    """Fetches all source records through the MCP provider and normalizes them."""

    def load_documents(self, provider: Optional[MCPProvider] = None) -> List[RAGDocument]:
        provider = provider or get_mcp_provider()
        records: List[MCPRecord] = []
        for kind in ("repositories", "issues", "pull_requests", "commits", "reviews"):
            records.extend(
                provider.search_github(kind=kind, limit=CANDIDATE_LIMIT)
            )
        records.extend(provider.search_gmail(kind="threads", limit=CANDIDATE_LIMIT))
        records.extend(provider.search_gmail(kind="messages", limit=CANDIDATE_LIMIT))
        records.extend(provider.get_cross_source_links())

        documents = [doc for doc in (to_rag_document(r) for r in records) if doc]
        documents.sort(key=lambda d: d.document_id)
        return documents


document_loader = DocumentLoader()

__all__ = ["DocumentLoader", "document_loader", "to_rag_document", "build_document_id"]
