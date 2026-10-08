from typing import Dict, List, Optional

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentContext, EvidenceRef, RetrievedRecord


class EvidenceAgent(BaseAgent):
    """Links every important claim to actual retrieved source records.

    Never fabricates evidence: a claim is only cited with records that exist
    in context.retrieved_records.
    """

    name = "Evidence Agent"

    def execute(self, context: AgentContext) -> AgentContext:
        by_source_id: Dict[str, RetrievedRecord] = {
            record.source_id: record for record in context.retrieved_records
        }

        evidence: List[EvidenceRef] = []
        cited_source_ids: set = set()

        for claim in context.claims:
            for source_id in claim.source_ids:
                record = by_source_id.get(source_id)
                if record is None or source_id in cited_source_ids:
                    continue
                cited_source_ids.add(source_id)
                evidence.append(
                    EvidenceRef(
                        claim=claim.claim,
                        source=record.source,
                        source_id=record.source_id,
                        record_type=record.record_type,
                        project_id=record.project_id or context.project_id,
                        title=record.title,
                        relevant_information=self._relevant_information(record),
                        relationship_information=self._relationship_information(record),
                        label=self._label(record),
                        author=self._author(record),
                        url="#gmail" if record.source == "Gmail" else "#github",
                    )
                )

        for index, ref in enumerate(evidence, start=1):
            ref.citation_id = str(index)

        context.evidence = evidence
        self.detail = f"{len(evidence)} evidence links across {len(cited_source_ids)} source records"
        return context

    def _relevant_information(self, record: RetrievedRecord) -> str:
        if record.record_type == "issue":
            return record.data.get("body") or record.summary
        if record.record_type == "pull_request":
            return record.data.get("summary") or record.summary
        if record.record_type in ("thread", "email"):
            return record.data.get("snippet") or record.data.get("body") or record.summary
        return record.summary

    def _relationship_information(self, record: RetrievedRecord) -> str:
        parts: List[str] = []
        for key, value in record.relationships.items():
            if not value:
                continue
            label = key.replace("_", " ")
            parts.append(f"{label}: {value}")
        return "; ".join(parts)

    def _label(self, record: RetrievedRecord) -> str:
        if record.record_type == "thread":
            return f"{record.source} Thread {record.source_id}"
        return f"{record.source} {record.source_id}"

    def _author(self, record: RetrievedRecord) -> str:
        if record.record_type == "issue":
            return record.data.get("author") or ""
        if record.record_type == "pull_request":
            return record.data.get("author") or record.data.get("assignee") or ""
        if record.record_type == "thread":
            participants = record.data.get("participants") or []
            return participants[0] if participants else ""
        if record.record_type == "email":
            return record.data.get("sender") or ""
        return ""
