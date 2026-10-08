from typing import List, Optional
from pydantic import BaseModel

from app.agents.models import EvidenceRef, RecommendedAction, TraceStage


class WorkflowRunSummary(BaseModel):
    run_id: str
    question: str
    project: str = ""
    project_id: str = ""
    status: str
    started_at: str = ""
    ended_at: str = ""
    total_duration_ms: float = 0.0
    stages: List[TraceStage] = []
    actions_awaiting_count: int = 0
    error: Optional[str] = None


class WorkflowRunDetail(WorkflowRunSummary):
    answer: str = ""
    confidence: str = ""
    target_release: str = ""
    target_date: str = ""
    release_status: str = ""
    risks: List[str] = []
    blockers: List[str] = []
    decisions: List[str] = []
    unresolved_actions: List[str] = []
    contradictions: List[str] = []
    recommended_actions: List[str] = []
    action_details: List[RecommendedAction] = []
    evidence: List[EvidenceRef] = []
    sources: List[str] = []
    failed_stage: Optional[str] = None


class WorkflowListResponse(BaseModel):
    runs: List[WorkflowRunSummary] = []
    count: int = 0
