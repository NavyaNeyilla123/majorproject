from abc import ABC, abstractmethod
from typing import List, Optional

from app.mcp.models import MCPHealth, MCPHealthReport, MCPRecord


class MCPProviderError(Exception):
    """Raised when the configured MCP provider cannot be resolved or used."""


class MCPProviderNotImplementedError(MCPProviderError):
    """Raised when the selected provider has no implementation yet (e.g. 'real')."""


class MCPProvider(ABC):
    """Isolation seam between agents and MCP-backed sources.

    CURRENT implementation: MockMCPProvider -> synthetic GitHub + Gmail JSON
    dataset via the existing repository layer. No network, no credentials.

    FUTURE implementation: a real MCP provider speaking to GitHub MCP and
    Gmail MCP servers. Selected with MCP_PROVIDER=real; until it exists the
    factory raises MCPProviderNotImplementedError instead of silently
    falling back to the mock provider.
    """

    provider_name: str = "abstract"

    # ---------------------------------------------------------------- GitHub

    @abstractmethod
    def search_github(
        self,
        query: str = "",
        project_id: str = "",
        kind: str = "issues",
        limit: int = 10,
    ) -> List[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_github_repository(self, repository_id: str) -> Optional[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_github_issue(self, number: int) -> Optional[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_github_pull_request(self, number: int) -> Optional[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_github_commit(self, sha: str) -> Optional[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_github_review(self, review_id: str) -> Optional[MCPRecord]:
        raise NotImplementedError

    # ----------------------------------------------------------------- Gmail

    @abstractmethod
    def search_gmail(
        self,
        query: str = "",
        project_id: str = "",
        kind: str = "threads",
        thread_id: str = "",
        limit: int = 10,
    ) -> List[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_gmail_thread(self, thread_id: str) -> Optional[MCPRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_gmail_message(self, message_id: str) -> Optional[MCPRecord]:
        raise NotImplementedError

    # ---------------------------------------------------------- Relationships

    @abstractmethod
    def get_cross_source_links(self, project_id: str = "") -> List[MCPRecord]:
        raise NotImplementedError

    # ----------------------------------------------------------------- Health

    @abstractmethod
    def health_check(self) -> MCPHealthReport:
        raise NotImplementedError

    @abstractmethod
    def github_health(self) -> MCPHealth:
        raise NotImplementedError

    @abstractmethod
    def gmail_health(self) -> MCPHealth:
        raise NotImplementedError
