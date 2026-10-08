from typing import List, Optional
from pydantic import BaseModel

from app.agents.models import EvidenceRef, RecommendedAction, TraceStage

class QueryRequest(BaseModel):
    question: str
    source_filter: Optional[List[str]] = None
    project_filter: Optional[str] = None

class QueryResponse(BaseModel):
    run_id: str
    question: str
    answer: str
    project: str
    target_release: str
    target_date: str
    status: str
    confidence: str
    risks: List[str]
    blockers: List[str]
    decisions: List[str]
    recommended_actions: List[str]
    action_details: List[RecommendedAction]
    evidence: List[EvidenceRef]
    sources: List[str]
    trace: List[TraceStage]
