from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.llm.models import LLMResponse


class RetrievedRecord(BaseModel):
    source: str
    record_type: str
    source_id: str
    project_id: str = ""
    title: str = ""
    summary: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    relationships: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRef(BaseModel):
    citation_id: str = ""
    claim: str = ""
    source: str
    source_id: str
    record_type: str
    project_id: str
    title: str
    relevant_information: str
    relationship_information: str = ""
    label: str = ""
    author: str = ""
    url: str = ""


class RecommendedAction(BaseModel):
    action: str
    priority: int
    owner: str = ""
    owner_source: str = ""
    depends_on: List[str] = Field(default_factory=list)
    evidence_source_ids: List[str] = Field(default_factory=list)
    status: str = "draft"


class AnalysisClaim(BaseModel):
    claim: str
    kind: str
    confidence: str = "medium"
    source_ids: List[str] = Field(default_factory=list)


class TraceStage(BaseModel):
    agent: str
    status: str = "pending"
    duration_ms: float = 0.0
    started_at: str = ""
    ended_at: str = ""
    detail: str = ""
    error: Optional[str] = None


class AgentContext(BaseModel):
    run_id: str
    question: str
    project: str = ""
    project_id: str = ""
    target_release: str = ""
    target_date: str = ""
    release_status: str = "Unknown"
    confidence: str = "low"
    sources: List[str] = Field(default_factory=list)
    record_types: List[str] = Field(default_factory=list)
    retrieval_objectives: List[str] = Field(default_factory=list)
    time_range: Optional[str] = None
    retrieved_records: List[RetrievedRecord] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    unresolved_actions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    claims: List[AnalysisClaim] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    action_details: List[RecommendedAction] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    final_answer: str = ""
    llm_response: Optional[LLMResponse] = None
    llm_used: bool = False
    execution_trace: List[TraceStage] = Field(default_factory=list)
    run_status: str = "running"
    failed_stage: Optional[str] = None
    error: Optional[str] = None
    started_at: str = ""
    ended_at: str = ""
    total_duration_ms: float = 0.0
