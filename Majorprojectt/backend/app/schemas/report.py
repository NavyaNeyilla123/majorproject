from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ReportRisk(BaseModel):
    risk: str
    impact_severity: str
    impact: str
    evidence: str
    refs: List[int] = Field(default_factory=list)


class ReportBlocker(BaseModel):
    title: str
    badge: str
    description: str


class ReportFinding(BaseModel):
    text: str
    refs: List[int] = Field(default_factory=list)


class ReportAction(BaseModel):
    action: str
    owner_due: str
    evidence: str = ""
    refs: List[int] = Field(default_factory=list)


class ReportCitation(BaseModel):
    index: int
    kind: str
    record: str
    timestamp: str


class ReportProvenance(BaseModel):
    status: str
    sources: str
    agent_run: str
    generation: str
    mcp: str
    rag: str
    llm: str
    note: str


class ReportRecent(BaseModel):
    report_id: str
    project_id: str
    title: str
    generated_at: str
    status: str


class ReportDocument(BaseModel):
    report_id: str
    project_id: str
    title: str
    reporting_period: str
    generated_at: str
    generated_by: str
    snapshot_time: str
    status: str
    executive_summary: str
    metrics: Dict[str, str] = Field(default_factory=dict)
    project_scope: str = ""
    workspace_context: str = ""
    major_risks: List[ReportRisk] = Field(default_factory=list)
    release_blocker: Optional[ReportBlocker] = None
    github_analysis: str = ""
    gmail_analysis: str = ""
    cross_source_findings: List[ReportFinding] = Field(default_factory=list)
    recommended_actions: List[ReportAction] = Field(default_factory=list)
    evidence_citations: List[ReportCitation] = Field(default_factory=list)
    provenance: ReportProvenance


class ReportGenerateResponse(BaseModel):
    report: Optional[ReportDocument] = None
    recent: List[ReportRecent] = Field(default_factory=list)
