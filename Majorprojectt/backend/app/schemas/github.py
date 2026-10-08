from typing import List, Optional
from pydantic import BaseModel
from app.models.github import Repository, Issue, PullRequest, Commit, Review

class GitHubStats(BaseModel):
    repository_count: int
    open_issue_count: int
    pull_request_count: int
    awaiting_review_count: int
    ready_to_merge_count: int
    median_review_time: str

class GitHubOverviewResponse(BaseModel):
    stats: GitHubStats
    repositories: List[Repository]
    issues: List[Issue]
    pull_requests: List[PullRequest]
