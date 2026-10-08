"""Builds the grounded LLM context and prompt (Step 9).

Everything shown to the model is projected from AgentContext: the LLM never
performs retrieval, never reads files and never calls tools. AgentContext is
imported lazily inside functions to keep this module free of import cycles
(app.agents.models depends on app.llm.models).
"""

import re
from typing import List

from app.llm.models import (
    LLMAnalysisSection,
    LLMClaim,
    LLMContext,
    LLMPrompt,
    LLMRecord,
)

MAX_RECORD_TEXT = 1000

SYSTEM_INSTRUCTIONS = """You are KnowledgeOps AI, a grounded release-assessment assistant.

Rules (mandatory):
- Answer ONLY from the evidence supplied in the user message. Do not use outside knowledge.
- Do not invent facts, source IDs, people, dates, approvals, completed actions or outcomes.
- Do not claim that anything was approved, merged, assigned, resolved or executed unless the supplied evidence states it.
- Distinguish evidence from inference: present facts as facts, assessments as assessments.
- "At risk" does not mean "delayed". Never claim a delay, postponement or confirmed delay unless a source explicitly says so.
- Recommendations are proposals only. Never present a recommendation as an action already taken.
- Cite sources in evidence_claims using ONLY source_ids that appear in the supplied evidence.
- If the evidence does not answer the question, say so plainly instead of guessing.
- Respond with a single JSON object only (no prose, no markdown fences), matching exactly this schema:
{"answer": string, "risks": [string], "blockers": [string], "decisions": [string], "recommended_actions": [string], "evidence_claims": [{"claim": string, "source_ids": [string], "source_types": [string], "confidence": number}], "confidence": number}
"""

_SECTIONS = (
    ("[QUESTION]", ["question"]),
    ("[PROJECT]", ["project", "target_release", "target_date", "release_status"]),
    ("[GITHUB EVIDENCE]", ["github_records"]),
    ("[GMAIL EVIDENCE]", ["gmail_records"]),
    ("[RAG RESULTS]", ["rag_records"]),
    ("[ANALYSIS]", ["analysis"]),
    ("[CROSS-SOURCE RELATIONSHIPS]", ["relationships"]),
)

_PUNCT_RE = re.compile(r"[_\-/.,:;!?()\[\]\"'`]+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "for", "and", "or", "to", "in", "on", "at", "with", "that",
    "this", "it", "its", "as", "by", "from", "not", "no", "but", "if",
    "into", "than", "then", "so", "such", "their", "there", "these",
    "those", "has", "have", "had", "do", "does", "did", "will", "would",
    "should", "could", "can", "may", "might", "must", "shall", "about",
}


def record_text(record) -> str:
    """Flatten a RetrievedRecord into comparable text for prompts and validation."""
    parts: List[str] = [record.source_id or "", record.title or "", record.summary or ""]
    data = getattr(record, "data", {}) or {}
    for key in ("body", "content", "message", "snippet", "description"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for key in (
        "status", "number", "severity", "ci_status", "next_step",
        "is_release_blocker", "security_reviewer_assigned", "linked_issue_number",
        "linked_pr_number",
    ):
        if key in data and not isinstance(data[key], (dict, list)):
            parts.append(f"{key}: {data[key]}")
    for value in data.get("provenance_facts", []) or []:
        if isinstance(value, str):
            parts.append(value)
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()[:MAX_RECORD_TEXT]


def content_tokens(text: str) -> set:
    """Lowercase content tokens (no punctuation, no stopwords) for overlap checks."""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return {
        token
        for token in _TOKEN_RE.findall(cleaned)
        if token not in _STOPWORDS and (len(token) >= 3 or token.isdigit())
    }


def _project_record(record) -> LLMRecord:
    return LLMRecord(
        source=record.source,
        record_type=record.record_type,
        source_id=record.source_id,
        title=record.title or "",
        text=record_text(record),
        relationships=dict(record.relationships or {}),
    )


def build_llm_context(context) -> LLMContext:
    """Project AgentContext into the read-only view handed to a provider."""
    from app.agents.models import AgentContext  # noqa: F401  (lazy; type-check only)

    github: List[LLMRecord] = []
    gmail: List[LLMRecord] = []
    rag: List[LLMRecord] = []
    links: List[LLMRecord] = []

    for record in context.retrieved_records:
        projected = _project_record(record)
        if record.record_type == "cross_source_link":
            links.append(projected)
        elif record.source == "GitHub":
            github.append(projected)
        elif record.source == "Gmail":
            gmail.append(projected)
        if (record.relationships or {}).get("rag_chunk"):
            rag.append(projected)

    analysis = LLMAnalysisSection(
        release_status=context.release_status,
        confidence=context.confidence,
        risks=list(context.risks),
        blockers=list(context.blockers),
        decisions=list(context.decisions),
        facts=list(context.facts),
        inferences=list(context.inferences),
        unresolved_actions=list(context.unresolved_actions),
        contradictions=list(context.contradictions),
        claims=[LLMClaim(claim=c.claim, source_ids=list(c.source_ids)) for c in context.claims],
    )

    return LLMContext(
        question=context.question,
        project=context.project,
        project_id=context.project_id,
        target_release=context.target_release,
        target_date=context.target_date,
        github_records=github,
        gmail_records=gmail,
        rag_records=rag,
        relationships=links,
        analysis=analysis,
    )


def _format_records(records: List[LLMRecord]) -> str:
    if not records:
        return "(none)"
    lines = [
        f"- [{record.source} {record.record_type} {record.source_id}] {record.title}: {record.text}"
        for record in records
    ]
    return "\n".join(lines)


def _format_analysis(section: LLMAnalysisSection) -> str:
    def block(label: str, items: List[str]) -> str:
        return f"{label}: " + ("; ".join(items) if items else "(none)")

    lines = [
        f"release_status: {section.release_status or '(unknown)'}",
        f"analysis_confidence: {section.confidence}",
        block("risks", section.risks),
        block("blockers", section.blockers),
        block("decisions", section.decisions),
        block("facts", section.facts),
        block("inferences", section.inferences),
        block("unresolved_actions", section.unresolved_actions),
        block("contradictions", section.contradictions),
    ]
    if section.claims:
        claim_lines = [
            f"- {claim.claim} (source_ids: {', '.join(claim.source_ids) or 'none'})"
            for claim in section.claims
        ]
        lines.append("analysis_claims:\n" + "\n".join(claim_lines))
    else:
        lines.append("analysis_claims: (none)")
    return "\n".join(lines)


def build_prompt(context: LLMContext) -> LLMPrompt:
    """Assemble the grounded prompt: fixed system rules + labeled evidence sections."""
    values = {
        "question": context.question or "(none)",
        "project": context.project or "(unknown)",
        "target_release": context.target_release or "(unknown)",
        "target_date": context.target_date or "(unknown)",
        "release_status": context.analysis.release_status or "(unknown)",
        "github_records": _format_records(context.github_records),
        "gmail_records": _format_records(context.gmail_records),
        "rag_records": _format_records(context.rag_records),
        "analysis": _format_analysis(context.analysis),
        "relationships": _format_records(context.relationships),
    }

    parts: List[str] = []
    for header, keys in _SECTIONS:
        parts.append(header)
        parts.extend(f"{key}: {values[key]}" for key in keys)
        parts.append("")

    parts.append("Respond with the JSON object only.")
    return LLMPrompt(system=SYSTEM_INSTRUCTIONS, user="\n".join(parts))
