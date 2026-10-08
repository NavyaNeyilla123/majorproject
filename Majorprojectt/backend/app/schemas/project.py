from typing import List, Optional
from pydantic import BaseModel
from app.models.project import Project
from app.models.github import Issue, PullRequest
from app.models.gmail import Thread

class ProjectDetailResponse(BaseModel):
    project: Project
    health_score: int
    open_issues_count: int
    active_prs_count: int
    relevant_emails_count: int
    linked_repositories_count: int
    issues: List[Issue]
    pull_requests: List[PullRequest]
    threads: List[Thread]
