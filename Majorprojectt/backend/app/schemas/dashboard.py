from typing import List, Optional
from pydantic import BaseModel

class DashboardMetrics(BaseModel):
    repositories_count: int
    open_issues_count: int
    active_prs_count: int
    relevant_emails_count: int
    project_risks_count: int
    pending_actions_count: int
    overall_health: str
    overall_health_score: Optional[int] = None
    prs_awaiting_review_count: int = 0
    prs_ready_to_merge_count: int = 0
    prs_draft_checks_count: int = 0
    emails_received_this_week: int = 0
    risks_need_attention: int = 0
    actions_due_today: int = 0
    github_org: str = ""

class DashboardRisk(BaseModel):
    id: str
    title: str
    severity: str
    project: str
    impact: str
    evidence_citation: str

class DashboardAction(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    owner: str
    project: str = ""
    due: str
    status: str
    evidence_citation: str

class DashboardActivity(BaseModel):
    type: str
    title: str
    description: str
    timestamp: str

class DashboardOverview(BaseModel):
    metrics: DashboardMetrics
    top_risks: List[DashboardRisk]
    pending_actions: List[DashboardAction]
    recent_activity: List[DashboardActivity]
