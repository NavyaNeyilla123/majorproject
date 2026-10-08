from typing import Optional, List
from pydantic import BaseModel, Field

class Repository(BaseModel):
    id: str
    name: str
    org: str
    project_id: str
    project_name: str
    open_issues_count: int = 0
    active_prs_count: int = 0
    health_status: str = "Healthy"
    synced_at: str = ""

class Issue(BaseModel):
    id: int
    number: int
    title: str
    repository: str
    project_id: Optional[str] = ""
    project_name: Optional[str] = ""
    author: Optional[str] = "unknown"
    assignee: Optional[str] = None
    status: str = "open"
    severity: str = "medium"
    is_release_blocker: bool = False
    labels: List[str] = Field(default_factory=list)
    body: Optional[str] = ""
    linked_pr_number: Optional[int] = None
    created_at: Optional[str] = ""
    updated_at: Optional[str] = ""

class PullRequest(BaseModel):
    id: int
    number: int
    title: str
    repository: str
    project_id: Optional[str] = ""
    project_name: Optional[str] = ""
    author: Optional[str] = "unknown"
    assignee: Optional[str] = None
    reviewers: List[str] = Field(default_factory=list)
    security_reviewer_assigned: bool = False
    ci_status: str = "passed"
    status: str = "open"
    pipeline_stage: str = "in_progress"
    age_hours: int = 0
    review_wait_hours: int = 0
    linked_issue_number: Optional[int] = None
    next_step: Optional[str] = ""
    summary: Optional[str] = ""
    created_at: Optional[str] = ""
    updated_at: Optional[str] = ""

class Commit(BaseModel):
    sha: str
    repository: str
    author: str
    message: str
    pr_number: Optional[int] = None
    timestamp: str = ""

class Review(BaseModel):
    id: str
    pr_number: int
    reviewer: str
    state: str
    body: Optional[str] = ""
    submitted_at: str = ""
