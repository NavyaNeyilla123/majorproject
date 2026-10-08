from typing import List, Optional
from app.core.data_loader import data_loader
from app.models.github import Repository, Issue, PullRequest, Commit, Review

class GitHubRepository:
    def get_repositories(self) -> List[Repository]:
        raw = data_loader.load_json("github/repositories.json")
        return [Repository(**item) for item in raw]
        
    def get_repository_by_id(self, repo_id: str) -> Optional[Repository]:
        for repo in self.get_repositories():
            if repo.id == repo_id or repo.name == repo_id:
                return repo
        return None

    def get_issues(self) -> List[Issue]:
        raw = data_loader.load_json("github/issues.json")
        return [Issue(**item) for item in raw]

    def get_open_issues(self) -> List[Issue]:
        return [issue for issue in self.get_issues() if issue.status == "open"]

    def get_issue_by_number(self, number: int) -> Optional[Issue]:
        for issue in self.get_issues():
            if issue.number == number:
                return issue
        return None

    def get_pull_requests(self) -> List[PullRequest]:
        raw = data_loader.load_json("github/pull_requests.json")
        return [PullRequest(**item) for item in raw]

    def get_pull_request_by_number(self, number: int) -> Optional[PullRequest]:
        for pr in self.get_pull_requests():
            if pr.number == number:
                return pr
        return None

    def get_commits(self) -> List[Commit]:
        raw = data_loader.load_json("github/commits.json")
        return [Commit(**item) for item in raw]

    def get_reviews(self) -> List[Review]:
        raw = data_loader.load_json("github/reviews.json")
        return [Review(**item) for item in raw]

github_repository = GitHubRepository()
