from typing import List, Optional
from app.repositories.github_repository import github_repository
from app.schemas.github import GitHubStats, GitHubOverviewResponse
from app.models.github import Repository, Issue, PullRequest, Commit, Review

class GitHubService:
    def get_overview(self) -> GitHubOverviewResponse:
        repos = github_repository.get_repositories()
        issues = github_repository.get_open_issues()
        prs = github_repository.get_pull_requests()
        
        awaiting_review = [p for p in prs if p.pipeline_stage == "awaiting_review"]
        ready_to_merge = [p for p in prs if p.pipeline_stage == "ready_to_merge"]
        
        stats = GitHubStats(
            repository_count=len(repos),
            open_issue_count=len(issues),
            pull_request_count=len(prs),
            awaiting_review_count=len(awaiting_review),
            ready_to_merge_count=len(ready_to_merge),
            median_review_time="N/A — not measured"
        )
        
        return GitHubOverviewResponse(
            stats=stats,
            repositories=repos,
            issues=issues,
            pull_requests=prs
        )

    def get_repositories(self) -> List[Repository]:
        return github_repository.get_repositories()

    def get_issues(self) -> List[Issue]:
        return github_repository.get_issues()

    def get_pull_requests(self) -> List[PullRequest]:
        return github_repository.get_pull_requests()

    def get_commits(self) -> List[Commit]:
        return github_repository.get_commits()

    def get_reviews(self) -> List[Review]:
        return github_repository.get_reviews()

github_service = GitHubService()
