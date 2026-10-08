"""Shared models for the LLM integration layer (Step 9).

No imports from app.agents here: this module must stay importable in both
directions (agents/models.py depends on LLMResponse, the prompt layer depends
on AgentContext only via function-local imports).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LLMError(Exception):
    """Base error for the LLM layer."""


class LLMUnavailableError(LLMError):
    """The configured provider cannot serve requests (no key, unknown name, transport error)."""


class LLMParseError(LLMError):
    """The provider returned something that is not a valid grounded response."""


class LLMPrompt(BaseModel):
    """Text handed to a provider: system instructions + grounded user context."""

    system: str = ""
    user: str = ""


class LLMRecord(BaseModel):
    """One retrieved record, projected for prompt display only."""

    source: str
    record_type: str
    source_id: str
    title: str = ""
    text: str = ""
    relationships: Dict[str, Any] = Field(default_factory=dict)


class LLMClaim(BaseModel):
    """Analysis claim echoed into the prompt (claim text + cited source ids)."""

    claim: str
    source_ids: List[str] = Field(default_factory=list)


class LLMAnalysisSection(BaseModel):
    """Analysis Agent output handed to the LLM as grounding context."""

    release_status: str = ""
    confidence: str = "low"
    risks: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    unresolved_actions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    claims: List[LLMClaim] = Field(default_factory=list)


class LLMContext(BaseModel):
    """Everything a provider is allowed to see; built only from AgentContext.

    The LLM never performs retrieval: question, records, analysis and links all
    arrive from the (MCP + RAG) Retrieval Agent and Analysis Agent stages.
    """

    question: str
    project: str = ""
    project_id: str = ""
    target_release: str = ""
    target_date: str = ""
    github_records: List[LLMRecord] = Field(default_factory=list)
    gmail_records: List[LLMRecord] = Field(default_factory=list)
    rag_records: List[LLMRecord] = Field(default_factory=list)
    relationships: List[LLMRecord] = Field(default_factory=list)
    analysis: LLMAnalysisSection = Field(default_factory=LLMAnalysisSection)


class EvidenceClaim(BaseModel):
    """A claim proposed by the LLM plus validator verdict fields."""

    claim: str
    source_ids: List[str] = Field(default_factory=list)
    source_types: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    supported: bool = False
    rejection_reason: str = ""


class LLMResponse(BaseModel):
    """Structured, parsed (not yet fully validated) LLM output."""

    answer: str
    risks: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    evidence_claims: List[EvidenceClaim] = Field(default_factory=list)
    confidence: float = 0.5


class LLMStatus(BaseModel):
    """GET /api/llm/status payload. Never contains credentials."""

    provider: str
    model: str
    configured: bool
    status: str  # healthy | configured | unavailable
    message: str = ""


def clamp_confidence(value: Any, default: float = 0.5) -> float:
    """Coerce an arbitrary confidence value to a float in [0, 1]."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(0.0, min(1.0, number))
