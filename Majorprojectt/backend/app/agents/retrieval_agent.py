from typing import Dict, List, Optional

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentContext, RetrievedRecord
from app.core.config import settings
from app.mcp import MCPProvider, MCPRecord, get_mcp_provider
from app.rag import rag_service

MAX_ISSUES = 5
MAX_PRS = 4
MAX_THREADS = 3
MAX_EMAILS_PER_THREAD = 4
MAX_CROSS_LINKS = 2
MAX_RAG_RECORDS = 5
CANDIDATE_LIMIT = 100

# chunk source_type -> (source, record_type) as used by the MCP records
RAG_RECORD_TYPES: Dict[str, tuple] = {
    "github_repository": ("GitHub", "repository"),
    "github_issue": ("GitHub", "issue"),
    "github_pull_request": ("GitHub", "pull_request"),
    "github_commit": ("GitHub", "commit"),
    "github_review": ("GitHub", "review"),
    "gmail_thread": ("Gmail", "thread"),
    "gmail_email": ("Gmail", "email"),
    "cross_source_link": ("Relationship", "cross_source_link"),
}


class RetrievalAgent(BaseAgent):
    """Retrieves relevant records for the planner's objectives via an MCPProvider.

    The provider is resolved lazily (MCP_PROVIDER env var, default 'mock'), so
    the agent itself never touches JSON files or repositories - all records
    flow through the MCPProvider seam. Selecting an unavailable provider
    raises a clear error instead of silently falling back.
    """

    name = "Retrieval Agent"

    def __init__(self, provider: Optional[MCPProvider] = None) -> None:
        super().__init__()
        self._provider_override = provider
        self.provider: Optional[MCPProvider] = provider

    def execute(self, context: AgentContext) -> AgentContext:
        provider = self._provider_override or get_mcp_provider()
        self.provider = provider

        objectives = set(context.retrieval_objectives)
        records: List[RetrievedRecord] = []

        issues = self._select_issues(provider, context.project_id, objectives)
        records.extend(issues)

        prs = self._select_pull_requests(provider, context.project_id, objectives, issues)
        records.extend(prs)

        threads = self._select_threads(provider, context.project_id, objectives)
        records.extend(threads)

        for record in threads:
            thread_id = record.data.get("id", "")
            emails = provider.search_gmail(
                kind="messages",
                thread_id=thread_id,
                limit=MAX_EMAILS_PER_THREAD,
            )
            for email in emails:
                records.append(self._email_record(email))

        records.extend(self._select_cross_links(provider, context, issues, prs, threads))

        records = self._merge_rag(context, records)

        context.retrieved_records = records
        by_type: Dict[str, int] = {}
        for record in records:
            by_type[record.record_type] = by_type.get(record.record_type, 0) + 1
        summary = ", ".join(f"{count} {rtype}" for rtype, count in by_type.items())
        rag_detail = getattr(self, "_rag_detail", "")
        suffix = f"; {rag_detail}" if rag_detail else ""
        scope = "" if context.project_id else " [workspace-wide: no project identified]"
        self.detail = f"{len(records)} records retrieved ({summary or 'none'}){suffix}{scope}"
        return context

    def _merge_rag(
        self, context: AgentContext, records: List[RetrievedRecord]
    ) -> List[RetrievedRecord]:
        """Append RAG chunks whose parent record is not already retrieved.

        The MCP selection above runs first and unmodified. Chunks are
        deduplicated by parent source_id; existing records are never touched.
        An empty index, unreachable store, or retrieval error degrades to
        MCP-only results with an explicit stage detail - the query never fails.
        """
        self._rag_detail = ""
        try:
            result = rag_service.search(
                context.question,
                filters={"project_id": context.project_id},
                top_k=settings.RAG_TOP_K,
            )
        except Exception as exc:  # graceful degradation
            self._rag_detail = f"rag unavailable ({type(exc).__name__}); mcp-only"
            return records

        if not result.chunks:
            self._rag_detail = "rag: empty index; mcp-only"
            return records

        existing_ids = {r.source_id for r in records}
        added = 0
        for chunk in result.chunks:
            if added >= MAX_RAG_RECORDS:
                break
            if not chunk.source_id or chunk.source_id in existing_ids:
                continue
            mapping = RAG_RECORD_TYPES.get(chunk.source_type)
            if mapping is None:
                continue
            source, record_type = mapping
            data = dict(chunk.metadata.get("data") or {})
            data["content"] = chunk.content
            data["rag_chunk_id"] = chunk.chunk_id
            score = round(chunk.rerank_score or chunk.score, 4)
            data["rag_score"] = score
            records.append(
                RetrievedRecord(
                    source=source,
                    record_type=record_type,
                    source_id=chunk.source_id,
                    project_id=chunk.project_id,
                    title=chunk.title,
                    summary=chunk.content[:280],
                    data=data,
                    relationships={"rag_chunk": chunk.chunk_id, "rag_score": score},
                )
            )
            existing_ids.add(chunk.source_id)
            added += 1

        if added:
            self._rag_detail = f"rag: {added} additional chunks merged"
        else:
            self._rag_detail = "rag: all top chunks already covered by mcp records"
        return records

    def _select_issues(
        self, provider: MCPProvider, project_id: str, objectives: set
    ) -> List[RetrievedRecord]:
        issues = provider.search_github(
            project_id=project_id, kind="issues", limit=CANDIDATE_LIMIT
        )
        blockers = [
            r
            for r in issues
            if r.data.get("is_release_blocker") and r.data.get("status") == "open"
        ]
        selected = blockers
        if "open issues" in objectives:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            open_rest = sorted(
                [r for r in issues if r.data.get("status") == "open" and r not in blockers],
                key=lambda r: severity_order.get(r.data.get("severity", "medium"), 9),
            )
            selected = selected + open_rest
        return [self._issue_record(r) for r in selected[:MAX_ISSUES]]

    def _select_pull_requests(
        self,
        provider: MCPProvider,
        project_id: str,
        objectives: set,
        issue_records: List[RetrievedRecord],
    ) -> List[RetrievedRecord]:
        prs = provider.search_github(
            project_id=project_id, kind="pull_requests", limit=CANDIDATE_LIMIT
        )
        linked_pr_numbers = {
            r.data.get("linked_pr_number")
            for r in issue_records
            if r.data.get("linked_pr_number")
        }
        retrieved_issue_numbers = {r.data.get("number") for r in issue_records}
        selected = [
            r
            for r in prs
            if r.data.get("number") in linked_pr_numbers
            or r.data.get("linked_issue_number") in retrieved_issue_numbers
        ]
        selected += [
            r
            for r in prs
            if r.data.get("status") == "awaiting_security_review" and r not in selected
        ]
        if not selected and "pull requests" in objectives:
            selected = [
                r
                for r in prs
                if r.data.get("status") in ("open", "awaiting_review", "review_pending")
            ][:MAX_PRS]
        return [self._pr_record(r) for r in selected[:MAX_PRS]]

    def _select_threads(
        self, provider: MCPProvider, project_id: str, objectives: set
    ) -> List[RetrievedRecord]:
        threads = provider.search_gmail(
            project_id=project_id, kind="threads", limit=CANDIDATE_LIMIT
        )
        blockers = [r for r in threads if r.data.get("is_release_blocker")]
        selected = blockers
        if not selected and (
            "approval status" in objectives or "release readiness" in objectives
        ):
            selected = threads
        return [self._thread_record(r) for r in selected[:MAX_THREADS]]

    def _select_cross_links(
        self,
        provider: MCPProvider,
        context: AgentContext,
        issue_records: List[RetrievedRecord],
        pr_records: List[RetrievedRecord],
        thread_records: List[RetrievedRecord],
    ) -> List[RetrievedRecord]:
        links = provider.get_cross_source_links(context.project_id)
        records: List[RetrievedRecord] = []
        issue_numbers = {r.data.get("number") for r in issue_records}
        pr_numbers = {r.data.get("number") for r in pr_records}
        thread_ids = {r.data.get("id") for r in thread_records}
        for link in links[:MAX_CROSS_LINKS]:
            blocker = link.data.get("primary_blocker") or {}
            gh_issue = blocker.get("github_issue") or {}
            gh_pr = blocker.get("github_pr") or {}
            gm_thread = blocker.get("gmail_thread") or {}
            issue_number = gh_issue.get("number")
            pr_number = gh_pr.get("number")
            gm_thread_id = gm_thread.get("id")
            related = bool(
                (issue_number is not None and issue_number in issue_numbers)
                or (pr_number is not None and pr_number in pr_numbers)
                or (gm_thread_id and gm_thread_id in thread_ids)
            )
            if not related and len(links) == 1:
                related = True
            if not related:
                continue
            records.append(
                RetrievedRecord(
                    source=link.source,
                    record_type=link.record_type,
                    source_id=link.source_id,
                    project_id=link.project_id,
                    title=link.data.get("description") or link.source_id,
                    summary=link.data.get("description") or "",
                    data=link.data,
                    relationships={
                        "github_issue": f"Issue #{issue_number}" if issue_number else "",
                        "github_pr": f"PR #{pr_number}" if pr_number else "",
                        "gmail_thread": gm_thread_id or "",
                    },
                )
            )
        return records

    def _issue_record(self, record: MCPRecord) -> RetrievedRecord:
        data = record.data
        relationships: Dict[str, object] = {}
        if data.get("linked_pr_number"):
            relationships["linked_pull_request"] = f"PR #{data['linked_pr_number']}"
        return RetrievedRecord(
            source=record.source,
            record_type=record.record_type,
            source_id=record.source_id,
            project_id=record.project_id,
            title=data.get("title", ""),
            summary=data.get("body") or "",
            data=data,
            relationships=relationships,
        )

    def _pr_record(self, record: MCPRecord) -> RetrievedRecord:
        data = record.data
        relationships: Dict[str, object] = {}
        if data.get("linked_issue_number"):
            relationships["linked_issue"] = f"Issue #{data['linked_issue_number']}"
        return RetrievedRecord(
            source=record.source,
            record_type=record.record_type,
            source_id=record.source_id,
            project_id=record.project_id,
            title=data.get("title", ""),
            summary=data.get("summary") or "",
            data=data,
            relationships=relationships,
        )

    def _thread_record(self, record: MCPRecord) -> RetrievedRecord:
        data = record.data
        return RetrievedRecord(
            source=record.source,
            record_type=record.record_type,
            source_id=record.source_id,
            project_id=record.project_id,
            title=data.get("subject", ""),
            summary=data.get("snippet") or "",
            data=data,
            relationships={},
        )

    def _email_record(self, record: MCPRecord) -> RetrievedRecord:
        data = record.data
        return RetrievedRecord(
            source=record.source,
            record_type=record.record_type,
            source_id=record.source_id,
            project_id=record.project_id,
            title=data.get("subject", ""),
            summary=(data.get("body") or "")[:280],
            data=data,
            relationships={"thread": data.get("thread_id", "")},
        )
