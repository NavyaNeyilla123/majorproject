"""MockMCPProvider: serves MCP tool calls from the synthetic JSON dataset.

Every method delegates to the existing repository layer (which reads
data/*.json on demand). There is no second copy of the dataset and no
hardcoded record identifiers - lookups are always dynamic.
"""

from typing import List, Optional

from app.mcp.base import MCPProvider, MCPProviderError
from app.mcp.github import GITHUB_MCP_ENDPOINT, GITHUB_SEARCH_KINDS
from app.mcp.gmail import GMAIL_MCP_ENDPOINT, GMAIL_SEARCH_KINDS
from app.mcp.health import build_health_report, dataset_health
from app.mcp.models import MCPHealth, MCPHealthReport, MCPRecord
from app.models.evidence import CrossSourceLink
from app.models.github import Commit, Issue, PullRequest, Repository, Review
from app.models.gmail import Email, Thread
from app.repositories.github_repository import github_repository
from app.repositories.gmail_repository import gmail_repository
from app.repositories.relationship_repository import relationship_repository

_UNLIMITED = 0


class MockMCPProvider(MCPProvider):
    """Mock implementation of the MCPProvider seam over the synthetic dataset."""

    provider_name = "mock"

    # ---------------------------------------------------------------- GitHub

    def search_github(
        self,
        query: str = "",
        project_id: str = "",
        kind: str = "issues",
        limit: int = 10,
    ) -> List[MCPRecord]:
        if kind not in GITHUB_SEARCH_KINDS:
            raise MCPProviderError(f"unsupported GitHub search kind: {kind!r}")
        if kind == "repositories":
            records = [self._repository_record(r) for r in github_repository.get_repositories()]
        elif kind == "issues":
            records = [self._issue_record(i) for i in github_repository.get_issues()]
        elif kind == "pull_requests":
            records = [self._pr_record(p) for p in github_repository.get_pull_requests()]
        elif kind == "commits":
            records = [self._commit_record(c) for c in github_repository.get_commits()]
        else:
            records = [self._review_record(r) for r in github_repository.get_reviews()]
        return self._filter(records, query, project_id, limit)

    def get_github_repository(self, repository_id: str) -> Optional[MCPRecord]:
        repo = github_repository.get_repository_by_id(repository_id)
        return self._repository_record(repo) if repo else None

    def get_github_issue(self, number: int) -> Optional[MCPRecord]:
        issue = github_repository.get_issue_by_number(number)
        return self._issue_record(issue) if issue else None

    def get_github_pull_request(self, number: int) -> Optional[MCPRecord]:
        pr = github_repository.get_pull_request_by_number(number)
        return self._pr_record(pr) if pr else None

    def get_github_commit(self, sha: str) -> Optional[MCPRecord]:
        for commit in github_repository.get_commits():
            if commit.sha == sha:
                return self._commit_record(commit)
        return None

    def get_github_review(self, review_id: str) -> Optional[MCPRecord]:
        for review in github_repository.get_reviews():
            if review.id == review_id:
                return self._review_record(review)
        return None

    # ----------------------------------------------------------------- Gmail

    def search_gmail(
        self,
        query: str = "",
        project_id: str = "",
        kind: str = "threads",
        thread_id: str = "",
        limit: int = 10,
    ) -> List[MCPRecord]:
        if kind not in GMAIL_SEARCH_KINDS:
            raise MCPProviderError(f"unsupported Gmail search kind: {kind!r}")
        if kind == "threads":
            records = [self._thread_record(t) for t in gmail_repository.get_threads()]
        else:
            emails = (
                gmail_repository.get_emails_by_thread_id(thread_id)
                if thread_id
                else gmail_repository.get_emails()
            )
            records = [self._email_record(e) for e in emails]
        return self._filter(records, query, project_id, limit)

    def get_gmail_thread(self, thread_id: str) -> Optional[MCPRecord]:
        thread = gmail_repository.get_thread_by_id(thread_id)
        return self._thread_record(thread) if thread else None

    def get_gmail_message(self, message_id: str) -> Optional[MCPRecord]:
        for email in gmail_repository.get_emails():
            if email.id == message_id:
                return self._email_record(email)
        return None

    # ---------------------------------------------------------- Relationships

    def get_cross_source_links(self, project_id: str = "") -> List[MCPRecord]:
        links = relationship_repository.get_cross_source_links()
        records = [self._cross_link_record(link) for link in links]
        return [r for r in records if not project_id or r.project_id == project_id]

    # ----------------------------------------------------------------- Health

    def health_check(self) -> MCPHealthReport:
        return build_health_report(self.provider_name, self.github_health(), self.gmail_health())

    def github_health(self) -> MCPHealth:
        def _count() -> int:
            return (
                len(github_repository.get_repositories())
                + len(github_repository.get_issues())
                + len(github_repository.get_pull_requests())
                + len(github_repository.get_commits())
                + len(github_repository.get_reviews())
            )

        return dataset_health("github", self.provider_name, GITHUB_MCP_ENDPOINT, _count)

    def gmail_health(self) -> MCPHealth:
        def _count() -> int:
            return len(gmail_repository.get_threads()) + len(gmail_repository.get_emails())

        return dataset_health("gmail", self.provider_name, GMAIL_MCP_ENDPOINT, _count)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _filter(records: List[MCPRecord], query: str, project_id: str, limit: int) -> List[MCPRecord]:
        if project_id:
            records = [r for r in records if r.project_id == project_id]
        if query:
            needle = query.lower()
            records = [r for r in records if MockMCPProvider._matches(r, needle)]
        if limit and limit > 0:
            records = records[:limit]
        return records

    @staticmethod
    def _matches(record: MCPRecord, needle: str) -> bool:
        text = " ".join(
            str(value) for value in record.data.values() if isinstance(value, (str, int, float))
        )
        return needle in text.lower()

    def _repository_record(self, repo: Repository) -> MCPRecord:
        return MCPRecord(
            source="GitHub",
            record_type="repository",
            source_id=repo.id,
            project_id=repo.project_id,
            data=repo.model_dump(),
        )

    def _issue_record(self, issue: Issue) -> MCPRecord:
        return MCPRecord(
            source="GitHub",
            record_type="issue",
            source_id=f"Issue #{issue.number}",
            project_id=issue.project_id,
            data=issue.model_dump(),
        )

    def _pr_record(self, pr: PullRequest) -> MCPRecord:
        return MCPRecord(
            source="GitHub",
            record_type="pull_request",
            source_id=f"PR #{pr.number}",
            project_id=pr.project_id,
            data=pr.model_dump(),
        )

    def _commit_record(self, commit: Commit) -> MCPRecord:
        repo = github_repository.get_repository_by_id(commit.repository)
        return MCPRecord(
            source="GitHub",
            record_type="commit",
            source_id=commit.sha,
            project_id=repo.project_id if repo else "",
            data=commit.model_dump(),
        )

    def _review_record(self, review: Review) -> MCPRecord:
        pr = github_repository.get_pull_request_by_number(review.pr_number)
        return MCPRecord(
            source="GitHub",
            record_type="review",
            source_id=review.id,
            project_id=pr.project_id if pr else "",
            data=review.model_dump(),
        )

    def _thread_record(self, thread: Thread) -> MCPRecord:
        return MCPRecord(
            source="Gmail",
            record_type="thread",
            source_id=thread.id,
            project_id=thread.project_id,
            data=thread.model_dump(),
        )

    def _email_record(self, email: Email) -> MCPRecord:
        return MCPRecord(
            source="Gmail",
            record_type="email",
            source_id=email.id,
            project_id=email.project_id,
            data=email.model_dump(),
            relationships={"thread": email.thread_id},
        )

    def _cross_link_record(self, link: CrossSourceLink) -> MCPRecord:
        return MCPRecord(
            source="Relationship",
            record_type="cross_source_link",
            source_id=link.id,
            project_id=link.project_id,
            data=link.model_dump(),
        )


mock_provider = MockMCPProvider()
