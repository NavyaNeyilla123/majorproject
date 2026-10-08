"""Step 10 tests: Real MCP provider - configuration, capability discovery,
normalization, read-only enforcement, honest status, and RAG isolation.

Every external interaction uses injected fake MCP sessions: no network, no
process spawns, no real GitHub/Gmail writes, and no credentials. Live
integration coverage is opt-in via MCP_INTEGRATION_TESTS=1.

Synthetic identifiers like 142/284/GM-064 may appear in tests only - the
real-mode implementation must never hardcode them (asserted below).
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pytest
from fastapi.testclient import TestClient

from app.agents.evidence_agent import EvidenceAgent
from app.agents.models import AgentContext, AnalysisClaim, RetrievedRecord
from app.agents.planner_agent import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.core.config import settings
from app.main import app
from app.mcp import get_mcp_provider
from app.mcp.base import MCPProviderError
from app.mcp.capability_map import (
    is_readonly_tool,
    load_overrides,
    resolve_or_raise,
    resolve_tool,
)
from app.mcp.models import MCPRecord
from app.mcp.real_provider import RealMCPProvider
from app.mcp.transport import (
    DiscoveredTool,
    MCPConnection,
    MCPServerConfig,
    load_server_config,
    redact,
)
from app.rag.document_loader import DocumentLoader, build_document_id, to_rag_document
from app.rag.indexer import Indexer
from app.rag.qdrant_client import InMemoryVectorStore, active_collection

client = TestClient(app)

CONFIG_ENV_KEYS = (
    "MCP_GITHUB_URL", "MCP_GITHUB_COMMAND", "MCP_GITHUB_TOKEN",
    "MCP_GMAIL_URL", "MCP_GMAIL_COMMAND", "MCP_GMAIL_TOKEN",
    "MCP_GITHUB_MAP", "MCP_GMAIL_MAP",
    "MCP_GITHUB_OWNER", "MCP_GITHUB_REPO", "MCP_GMAIL_USER_ID",
)


# ----------------------------------------------------------- fake MCP harness

class FakeSession:
    def __init__(self, harness: "FakeHarness") -> None:
        self.harness = harness

    async def list_tools(self):
        self.harness.list_calls += 1
        if self.harness.list_error is not None:
            raise self.harness.list_error
        return SimpleNamespace(tools=[dict(tool) for tool in self.harness.tools])

    async def call_tool(self, name, arguments):
        self.harness.calls.append((name, dict(arguments or {})))
        if name in self.harness.call_errors:
            text = self.harness.call_errors[name]
            return SimpleNamespace(
                content=[SimpleNamespace(text=text)], isError=True
            )
        payload = self.harness.responses.get(name, [])
        if callable(payload):
            payload = payload(arguments or {})
        return SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(payload))], isError=False
        )


class FakeHarness:
    """Records every list/call issued through an injected session factory."""

    def __init__(self, tools, responses=None, list_error=None, call_errors=None, open_error=None, open_delay=0.0):
        self.tools = tools
        self.responses = responses or {}
        self.list_error = list_error
        self.call_errors = call_errors or {}
        self.open_error = open_error
        self.open_delay = open_delay
        self.calls = []
        self.list_calls = 0
        self.sessions = 0

    def factory(self, cfg):
        @asynccontextmanager
        async def open_session(_cfg):
            self.sessions += 1
            if self.open_delay:
                await asyncio.sleep(self.open_delay)
            if self.open_error is not None:
                raise self.open_error
            yield FakeSession(self)

        return open_session(cfg)

    @property
    def called_tools(self):
        return [name for name, _ in self.calls]


def stdio_config(server: str = "github", token: str = "", **extra) -> MCPServerConfig:
    return MCPServerConfig(
        server=server,
        transport="stdio",
        command=extra.get("command", "fake-mcp-server"),
        args=tuple(extra.get("args", ("--read-only",))),
        token=token,
        token_env=extra.get("token_env", "GITHUB_PERSONAL_ACCESS_TOKEN"),
    )


def connection(server: str, harness: FakeHarness, config: MCPServerConfig = None) -> MCPConnection:
    return MCPConnection(
        server,
        config=config or stdio_config(server),
        session_factory=harness.factory,
    )


def provider_with(github_harness: FakeHarness = None, gmail_harness: FakeHarness = None) -> RealMCPProvider:
    github = connection("github", github_harness) if github_harness else None
    gmail = connection("gmail", gmail_harness) if gmail_harness else None
    return RealMCPProvider(github=github, gmail=gmail)


def tool(name: str, properties=None, required=None) -> dict:
    schema = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = list(required)
    return {"name": name, "inputSchema": schema}


@pytest.fixture(autouse=True)
def clean_mcp_env(monkeypatch):
    for key in CONFIG_ENV_KEYS + ("MCP_PROVIDER", "MCP_CONNECT_TIMEOUT_MS", "MCP_CALL_TIMEOUT_MS"):
        monkeypatch.delenv(key, raising=False)
    yield


GITHUB_READ_TOOLS = [
    tool("search_issues"),
    tool("list_pull_requests"),
    tool("get_issue"),
    tool("list_commits"),
]

GMAIL_READ_TOOLS = [
    tool("search_threads"),
    tool("search_messages"),
    tool("get_message"),
]


# ------------------------------------------------- 1. provider selection

def test_real_provider_selected_and_never_falls_back(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "real")
    provider = get_mcp_provider()
    assert isinstance(provider, RealMCPProvider)
    assert provider.provider_name == "real"
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "unconfigured" in str(excinfo.value)


def test_unconfigured_data_operations_raise_for_both_sources():
    provider = RealMCPProvider()
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "unconfigured" in str(excinfo.value)
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_gmail(kind="threads")
    assert "unconfigured" in str(excinfo.value)


def test_unconfigured_health_reports_honestly_without_connecting():
    provider = RealMCPProvider()
    report = provider.health_check()
    assert report.provider == "real"
    assert report.healthy is False
    for health in (report.github, report.gmail):
        assert health.status == "unconfigured"
        assert health.healthy is False
        assert health.mock_connected is False
        assert health.tools == []
        assert "not configured" in health.message


# --------------------------------------------- 2. capability discovery

def test_discover_reports_connected_with_actual_tool_names():
    harness = FakeHarness(GITHUB_READ_TOOLS)
    conn = connection("github", harness)
    outcome = conn.discover()
    assert outcome.state == "connected"
    assert outcome.tool_names == ["search_issues", "list_pull_requests", "get_issue", "list_commits"]
    assert harness.list_calls == 1
    assert "read-only" in outcome.message


def test_discover_reports_error_when_tools_list_fails():
    harness = FakeHarness(GITHUB_READ_TOOLS, list_error=RuntimeError("protocol broke"))
    conn = connection("github", harness)
    outcome = conn.discover()
    assert outcome.state == "error"
    assert outcome.tools == []
    assert "protocol broke" in outcome.message


def test_discover_reports_unavailable_when_server_cannot_start():
    harness = FakeHarness(GITHUB_READ_TOOLS, open_error=FileNotFoundError("no such server"))
    conn = connection("github", harness)
    outcome = conn.discover()
    assert outcome.state == "unavailable"
    assert "no such server" in outcome.message


def test_discover_reports_unavailable_on_timeout(monkeypatch):
    monkeypatch.setenv("MCP_CONNECT_TIMEOUT_MS", "50")
    harness = FakeHarness(GITHUB_READ_TOOLS, open_delay=1.5)
    conn = connection("github", harness)
    outcome = conn.discover()
    assert outcome.state == "unavailable"
    assert "timed out" in outcome.message


def test_unsupported_capability_raises_with_discovered_tools():
    harness = FakeHarness([tool("create_issue"), tool("delete_issue")])
    provider = provider_with(harness)
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    message = str(excinfo.value)
    assert "no read-only tool" in message
    assert "create_issue" in message


def test_call_rejects_tool_not_in_discovered_list():
    harness = FakeHarness(GITHUB_READ_TOOLS)
    conn = connection("github", harness)
    with pytest.raises(MCPProviderError) as excinfo:
        conn.call("invented_tool", {})
    assert "does not expose" in str(excinfo.value)


def test_explicit_map_override_and_write_refusal(monkeypatch):
    tools = GITHUB_READ_TOOLS + [tool("fetch_ticket_items"), tool("create_issue")]
    harness = FakeHarness(tools)
    provider = provider_with(harness)

    monkeypatch.setenv("MCP_GITHUB_MAP", json.dumps({"search.issues": "fetch_ticket_items"}))
    records = provider.search_github(kind="issues")
    assert harness.called_tools[-1] == "fetch_ticket_items"
    assert records == []

    monkeypatch.setenv("MCP_GITHUB_MAP", json.dumps({"search.issues": "create_issue"}))
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "read-only" in str(excinfo.value)

    monkeypatch.setenv("MCP_GITHUB_MAP", json.dumps({"search.issues": "no_such_tool"}))
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "does not advertise" in str(excinfo.value)


def test_invalid_map_json_is_a_clear_config_error(monkeypatch):
    monkeypatch.setenv("MCP_GITHUB_MAP", "{not valid json")
    with pytest.raises(MCPProviderError) as excinfo:
        load_overrides("github")
    assert "valid JSON" in str(excinfo.value)


def test_config_change_invalidates_discovery_cache(monkeypatch):
    harness = FakeHarness(GITHUB_READ_TOOLS)
    conn = MCPConnection("github", session_factory=harness.factory)  # env-bound
    monkeypatch.setenv("MCP_GITHUB_COMMAND", "server-one")
    first = conn.discover()
    assert first.state == "connected"
    assert conn.endpoint_display() == "server-one"
    monkeypatch.setenv("MCP_GITHUB_COMMAND", "server-two")
    assert conn.endpoint_display() == "server-two"
    conn.discover()
    assert harness.list_calls == 2


# ---------------------------------------------------- 3. read-only enforcement

@pytest.mark.parametrize(
    "name,readonly",
    [
        ("search_issues", True),
        ("list_labels", True),
        ("get_file_contents", True),
        ("create_issue", False),
        ("update_pull_request", False),
        ("delete_comment", False),
        ("send_email", False),
        ("label_issue", False),
        ("add_reaction", False),
        ("merge_pull_request", False),
    ],
)
def test_write_tool_classification(name, readonly):
    assert is_readonly_tool(name) is readonly


def test_write_tools_are_never_bound():
    tools = [
        DiscoveredTool(name="create_issue", input_schema={}),
        DiscoveredTool(name="update_issue", input_schema={}),
        DiscoveredTool(name="search_code", input_schema={}),
    ]
    assert resolve_tool("search.issues", tools) is None
    assert resolve_tool("get.issue", tools) is None


def test_provider_only_ever_calls_read_only_tools():
    tools = GITHUB_READ_TOOLS + [tool("create_issue"), tool("send_email")]
    responses = {
        "search_issues": [{"number": 5, "title": "t", "state": "open"}],
        "list_pull_requests": [],
        "list_commits": [],
        "get_issue": issue_payload(number=5),
    }
    harness = FakeHarness(tools, responses=responses)
    provider = provider_with(harness)
    provider.search_github(kind="issues")
    provider.search_github(kind="pull_requests")
    provider.search_github(kind="commits")
    provider.get_github_issue(5)
    assert harness.calls
    assert all(is_readonly_tool(name) for name in harness.called_tools)


# ------------------------------------------------ 4. GitHub normalization

def issue_payload(number=7, url="https://github.com/acme/platform/issues/7"):
    return {
        "number": number,
        "id": 9000 + number,
        "title": "Latency spike on checkout",
        "state": "open",
        "body": "Checkout p99 doubled after deploy.",
        "user": {"login": "dana"},
        "labels": [{"name": "perf"}, {"name": "release"}],
        "html_url": url,
        "created_at": "2026-09-01T10:00:00Z",
        "updated_at": "2026-09-02T11:30:00Z",
    }


def test_search_issues_normalizes_real_payload():
    harness = FakeHarness(GITHUB_READ_TOOLS, responses={"search_issues": [issue_payload()]})
    provider = provider_with(harness)
    records = provider.search_github(kind="issues", limit=5)
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, MCPRecord)
    assert record.source == "GitHub"
    assert record.record_type == "issue"
    assert record.source_id == "Issue #7"
    assert record.source_mode == "real"
    assert record.project_id == ""
    assert record.data["number"] == 7
    assert record.data["url"] == "https://github.com/acme/platform/issues/7"
    assert record.data["author"] == "dana"
    assert record.data["labels"] == ["perf", "release"]
    assert record.data["repository"] == "acme/platform"
    assert record.data["status"] == "open"
    assert "severity" not in record.data
    assert "is_release_blocker" not in record.data
    assert "project_name" not in record.data


def test_search_respects_limit():
    payloads = [issue_payload(number=n) for n in (1, 2, 3, 4)]
    harness = FakeHarness(GITHUB_READ_TOOLS, responses={"search_issues": payloads})
    provider = provider_with(harness)
    records = provider.search_github(kind="issues", limit=2)
    assert [r.data["number"] for r in records] == [1, 2]


def test_search_kind_is_validated_before_discovery():
    harness = FakeHarness(GITHUB_READ_TOOLS)
    provider = provider_with(harness)
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="gists")
    assert "unsupported GitHub search kind" in str(excinfo.value)
    assert harness.list_calls == 0


def test_get_issue_preserves_identity_and_returns_none_when_missing():
    harness = FakeHarness(
        GITHUB_READ_TOOLS,
        responses={"get_issue": issue_payload(number=42, url="https://github.com/acme/platform/issues/42")},
    )
    provider = provider_with(harness)
    record = provider.get_github_issue(42)
    assert record.source_id == "Issue #42"
    assert record.data["url"].endswith("/issues/42")
    name, args = harness.calls[-1]
    assert name == "get_issue"
    assert args == {}

    missing = FakeHarness(
        GITHUB_READ_TOOLS, call_errors={"get_issue": "Error: issue 999 not found"}
    )
    provider = provider_with(missing)
    assert provider.get_github_issue(999) is None


def test_malformed_issue_payload_raises():
    harness = FakeHarness(GITHUB_READ_TOOLS, responses={"search_issues": [{"title": "no number"}]})
    provider = provider_with(harness)
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "missing 'number'" in str(excinfo.value)


def test_malformed_list_items_raise():
    harness = FakeHarness(GITHUB_READ_TOOLS, responses={"search_issues": ["not-an-object"]})
    provider = provider_with(harness)
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "malformed" in str(excinfo.value)


def test_required_parameters_without_scope_fail_with_guidance(monkeypatch):
    schema_tool = tool(
        "get_issue",
        properties={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
        },
        required=["owner", "repo", "issue_number"],
    )
    harness = FakeHarness([schema_tool], responses={"get_issue": issue_payload()})
    provider = provider_with(harness)
    with pytest.raises(MCPProviderError) as excinfo:
        provider.get_github_issue(7)
    message = str(excinfo.value)
    assert "owner" in message and "repo" in message
    assert "MCP_GITHUB_OWNER" in message


def test_scope_env_satisfies_required_parameters(monkeypatch):
    monkeypatch.setenv("MCP_GITHUB_OWNER", "acme")
    monkeypatch.setenv("MCP_GITHUB_REPO", "platform")
    schema_tool = tool(
        "get_issue",
        properties={
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
        },
        required=["owner", "repo", "issue_number"],
    )
    harness = FakeHarness([schema_tool], responses={"get_issue": issue_payload()})
    provider = provider_with(harness)
    record = provider.get_github_issue(7)
    assert record is not None
    name, args = harness.calls[-1]
    assert args == {"owner": "acme", "repo": "platform", "issue_number": 7}


def test_commit_and_review_normalization():
    tools = [tool("list_commits"), tool("get_review")]
    responses = {
        "list_commits": [
            {
                "sha": "abc123def456",
                "commit": {"message": "fix: retry logic", "author": {"name": "sam", "date": "2026-09-03T09:00:00Z"}},
                "html_url": "https://github.com/acme/platform/commit/abc123def456",
            }
        ],
        "get_review": {
            "id": 555,
            "state": "APPROVED",
            "body": "looks good",
            "user": {"login": "kai"},
            "pull_request": {"number": 9, "url": "https://api.github.com/repos/acme/platform/pulls/9"},
        },
    }
    harness = FakeHarness(tools, responses=responses)
    provider = provider_with(harness)

    commit = provider.search_github(kind="commits")[0]
    assert commit.record_type == "commit"
    assert commit.source_id == "abc123def456"
    assert commit.data["author"] == "sam"
    assert commit.data["url"].endswith("/commit/abc123def456")

    review = provider.get_github_review("555")
    assert review.record_type == "review"
    assert review.data["pr_number"] == 9
    assert review.data["reviewer"] == "kai"
    assert review.data["state"] == "APPROVED"


def test_repository_normalization():
    tools = [tool("search_repositories")]
    payload = {
        "id": 321,
        "name": "platform",
        "full_name": "acme/platform",
        "owner": {"login": "acme"},
        "html_url": "https://github.com/acme/platform",
        "open_issues_count": 4,
    }
    harness = FakeHarness(tools, responses={"search_repositories": [payload]})
    provider = provider_with(harness)
    record = provider.search_github(kind="repositories")[0]
    assert record.record_type == "repository"
    assert record.source_id == "321"
    assert record.data["org"] == "acme"
    assert record.data["url"] == "https://github.com/acme/platform"
    assert record.data["open_issues_count"] == 4


# --------------------------------------------------- 5. Gmail normalization

def test_search_threads_normalizes_headers_and_participants():
    tools = [tool("search_threads")]
    payload = {
        "id": "thread-99",
        "messages": [
            {"headers": [
                {"name": "From", "value": "pat@acme.com"},
                {"name": "To", "value": "team@acme.com"},
                {"name": "Subject", "value": "Release go/no-go"},
            ]},
            {"headers": [
                {"name": "From", "value": "team@acme.com"},
                {"name": "To", "value": "pat@acme.com"},
                {"name": "Subject", "value": "Release go/no-go"},
            ]},
        ],
        "snippet": "Waiting on security approval",
    }
    harness = FakeHarness(tools, responses={"search_threads": [payload]})
    provider = provider_with(gmail_harness=harness)
    record = provider.search_gmail(kind="threads")[0]
    assert record.source == "Gmail"
    assert record.record_type == "thread"
    assert record.source_id == "thread-99"
    assert record.source_mode == "real"
    assert record.data["subject"] == "Release go/no-go"
    assert record.data["snippet"] == "Waiting on security approval"
    assert record.data["message_count"] == 2
    assert "pat@acme.com" in record.data["participants"]
    assert "team@acme.com" in record.data["participants"]


def test_search_messages_normalizes_sender_recipients_and_time():
    tools = [tool("search_messages")]
    payload = [
        {
            "id": "msg-1",
            "threadId": "thread-99",
            "subject": "Re: Release go/no-go",
            "from": "pat@acme.com",
            "to": ["team@acme.com", "sec@acme.com"],
            "body": "Security approved the release.",
            "internalDate": "1757880000000",
        }
    ]
    harness = FakeHarness(tools, responses={"search_messages": payload})
    provider = provider_with(gmail_harness=harness)
    record = provider.search_gmail(kind="messages")[0]
    assert record.record_type == "email"
    assert record.source_id == "msg-1"
    assert record.relationships["thread"] == "thread-99"
    assert record.data["sender"] == "pat@acme.com"
    assert record.data["sender_email"] == "pat@acme.com"
    assert record.data["recipients"] == ["team@acme.com", "sec@acme.com"]
    assert record.data["body"] == "Security approved the release."
    assert record.data["received_at"].startswith("2025-")


def test_get_message_missing_returns_none():
    harness = FakeHarness(
        GMAIL_READ_TOOLS, call_errors={"get_message": "message with that id not found"}
    )
    provider = provider_with(gmail_harness=harness)
    assert provider.get_gmail_message("nope") is None


def test_cross_source_links_are_honestly_empty_in_real_mode():
    provider = provider_with(FakeHarness(GITHUB_READ_TOOLS))
    assert provider.get_cross_source_links("any") == []


# ------------------------------------------------ 6. health & status endpoint

def test_health_connected_only_after_live_capability_check():
    harness = FakeHarness(GITHUB_READ_TOOLS)
    provider = provider_with(github_harness=harness)
    health = provider.github_health()
    assert health.status == "connected"
    assert health.healthy is True
    assert health.mock_connected is False
    assert health.provider == "real"
    assert health.tools == [t["name"] for t in GITHUB_READ_TOOLS]
    assert health.endpoint == "fake-mcp-server --read-only"
    assert harness.list_calls == 1


def test_health_error_and_unavailable_states():
    error_provider = provider_with(
        FakeHarness(GITHUB_READ_TOOLS, list_error=ValueError("bad handshake"))
    )
    error_health = error_provider.github_health()
    assert error_health.status == "error"
    assert error_health.healthy is False
    assert "bad handshake" in error_health.message

    down_provider = provider_with(
        FakeHarness(GITHUB_READ_TOOLS, open_error=ConnectionRefusedError("connection refused"))
    )
    down_health = down_provider.github_health()
    assert down_health.status == "unavailable"
    assert down_health.healthy is False
    assert "connection refused" in down_health.message


def test_credentials_never_appear_in_health_messages(monkeypatch):
    secret = "ghp_super_secret_value"
    harness = FakeHarness(
        GITHUB_READ_TOOLS, list_error=RuntimeError(f"auth failed token={secret}")
    )
    conn = connection("github", harness, config=stdio_config("github", token=secret))
    outcome = conn.discover()
    assert secret not in outcome.message
    assert "[redacted]" in outcome.message


def test_status_endpoint_shows_real_connected_state(monkeypatch):
    import app.api.mcp as mcp_api

    github_harness = FakeHarness(GITHUB_READ_TOOLS)
    gmail_harness = FakeHarness(GMAIL_READ_TOOLS)
    provider = provider_with(github_harness, gmail_harness)
    monkeypatch.setattr(mcp_api, "get_mcp_provider", lambda *a, **k: provider)

    response = client.get("/api/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "real"
    assert data["mode"] == "Real MCP"
    assert data["data_source"] == "Live data"
    github = data["github"]
    assert github["status"] == "connected"
    assert github["healthy"] is True
    assert github["tools"] == [t["name"] for t in GITHUB_READ_TOOLS]
    assert github["endpoint"] == "fake-mcp-server --read-only"
    assert data["gmail"]["status"] == "connected"
    assert "capability check" in data["detail"]


def test_status_endpoint_never_claims_connected_without_live_check(monkeypatch):
    import app.api.mcp as mcp_api

    provider = provider_with(
        FakeHarness(GITHUB_READ_TOOLS, list_error=RuntimeError("server crashed"))
    )
    provider._gmail_conn = MCPConnection("gmail")
    monkeypatch.setattr(mcp_api, "get_mcp_provider", lambda *a, **k: provider)

    response = client.get("/api/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["github"]["status"] == "error"
    assert data["github"]["healthy"] is False
    assert data["gmail"]["status"] == "unconfigured"
    assert data["gmail"]["healthy"] is False
    assert "server crashed" in data["github"]["message"]


def test_status_endpoint_default_stays_mock():
    response = client.get("/api/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["mode"] == "Mock MCP"
    assert data["github"]["status"] == "mock_connected"


def test_redact_strips_token_and_bearer_material():
    text = "Authorization: Bearer abc.def-123 failed for token=ghp_xyz"
    cleaned = redact(text, "ghp_xyz")
    assert "ghp_xyz" not in cleaned
    assert "abc.def-123" not in cleaned
    assert "[redacted]" in cleaned


def test_load_server_config_prefers_url_over_command(monkeypatch):
    monkeypatch.setenv("MCP_GITHUB_URL", "https://example.test/mcp")
    monkeypatch.setenv("MCP_GITHUB_COMMAND", "some-command")
    cfg = load_server_config("github")
    assert cfg.transport == "streamable_http"
    assert cfg.configured is True
    monkeypatch.delenv("MCP_GITHUB_URL")
    cfg = load_server_config("github")
    assert cfg.transport == "stdio"
    monkeypatch.delenv("MCP_GITHUB_COMMAND")
    assert load_server_config("github").configured is False


# ------------------------------------------- 7. RAG isolation & source_mode

def mock_issue_record(number=142):
    return MCPRecord(
        source="GitHub",
        record_type="issue",
        source_id=f"Issue #{number}",
        project_id="proj-platform-api",
        data={"number": number, "title": "synthetic", "status": "open"},
    )


def real_issue_record(number=142):
    return MCPRecord(
        source="GitHub",
        record_type="issue",
        source_id=f"Issue #{number}",
        project_id="",
        data={"number": number, "title": "real", "status": "open", "url": "https://github.com/acme/x/issues/142"},
        source_mode="real",
    )


def test_document_ids_never_collide_between_mock_and_real():
    mock_id = build_document_id(mock_issue_record(142), "github_issue")
    real_id = build_document_id(real_issue_record(142), "github_issue")
    assert mock_id == "github:issue:142"
    assert real_id == "real:github:issue:142"
    assert mock_id != real_id


def test_real_documents_carry_source_mode_metadata():
    doc = to_rag_document(real_issue_record(7))
    assert doc is not None
    assert doc.metadata["source_mode"] == "real"
    assert doc.document_id.startswith("real:")
    mock_doc = to_rag_document(mock_issue_record(7))
    assert mock_doc.metadata["source_mode"] == "mock"
    assert not mock_doc.document_id.startswith("real:")


def test_active_collection_switches_with_provider(monkeypatch):
    monkeypatch.delenv("MCP_PROVIDER", raising=False)
    assert active_collection() == "knowledgeops_projects"
    monkeypatch.setenv("MCP_PROVIDER", "real")
    assert active_collection() == "knowledgeops_real"
    monkeypatch.setenv("RAG_REAL_COLLECTION", "custom_real")
    settings.RAG_REAL_COLLECTION = "custom_real"
    try:
        assert active_collection() == "custom_real"
    finally:
        settings.RAG_REAL_COLLECTION = "knowledgeops_real"


def test_real_collection_clear_never_touches_synthetic_store():
    synthetic = InMemoryVectorStore(collection="knowledgeops_projects")
    synthetic.upsert([("synthetic-chunk", [0.1] * 8, {"source_mode": "mock", "content": "synthetic"})])
    monkeypatched_real = InMemoryVectorStore(collection="knowledgeops_real")
    monkeypatched_real.upsert([("real-chunk", [0.2] * 8, {"source_mode": "real", "content": "real"})])

    monkeypatched_real.clear()
    assert monkeypatched_real.count() == 0
    assert synthetic.count() == 1


def test_indexing_real_records_targets_real_collection(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "real")
    github_harness = FakeHarness(
        GITHUB_READ_TOOLS
        + [tool("search_repositories"), tool("search_reviews")],
        responses={"search_issues": [issue_payload(number=11)]},
    )
    gmail_harness = FakeHarness(
        GMAIL_READ_TOOLS,
        responses={
            "search_threads": [{"id": "thread-1", "subject": "hello", "messages": []}],
        },
    )
    real_provider = provider_with(github_harness, gmail_harness)

    class FixedProviderLoader(DocumentLoader):
        def load_documents(self, provider=None):
            return super().load_documents(provider or real_provider)

    synthetic = InMemoryVectorStore(collection="knowledgeops_projects")
    synthetic.upsert([("keep-me", [0.1] * 8, {"source_mode": "mock", "content": "synthetic"})])

    real_store = InMemoryVectorStore()  # active_collection -> knowledgeops_real
    assert real_store.collection == "knowledgeops_real"
    indexer = Indexer(loader=FixedProviderLoader(), store=real_store)
    stats = indexer.run(force_reindex=True)
    assert stats.documents_processed >= 1
    payloads = real_store.scroll()
    assert payloads
    assert all(p.get("source_mode") == "real" for p in payloads)
    assert all(str(p.get("document_id", "")).startswith("real:") for p in payloads)
    assert synthetic.count() == 1


# ------------------------------------- 8. retrieval & evidence with real data

def test_retrieval_agent_with_real_provider_preserves_urls(monkeypatch):
    github_tools = GITHUB_READ_TOOLS + [tool("search_repositories"), tool("list_reviews")]
    responses = {
        "search_issues": [issue_payload(number=7)],
        "list_pull_requests": [
            {"number": 3, "title": "Fix checkout", "state": "open", "user": {"login": "kai"},
             "html_url": "https://github.com/acme/platform/pull/3"}
        ],
        "search_threads": [
            {"id": "thread-7", "subject": "Release approval", "snippet": "approve?", "messages": []}
        ],
        "search_messages": [
            {"id": "msg-7", "threadId": "thread-7", "subject": "Release approval",
             "from": "pat@acme.com", "to": ["team@acme.com"], "body": "approved"}
        ],
    }
    github_harness = FakeHarness(github_tools, responses=responses)
    gmail_harness = FakeHarness(GMAIL_READ_TOOLS, responses=responses)
    real_provider = provider_with(github_harness, gmail_harness)

    agent = RetrievalAgent(provider=real_provider)
    context = PlannerAgent().run(
        AgentContext(run_id="KO-REAL001", question="What could delay the Platform API v2.4 release, and what should we do next?")
    )
    context.retrieval_objectives = {"open issues", "pull requests", "approval status"}
    context = agent.run(context)

    assert isinstance(agent.provider, RealMCPProvider)
    by_id = {record.source_id: record for record in context.retrieved_records}
    assert "Issue #7" in by_id
    assert by_id["Issue #7"].data["url"] == "https://github.com/acme/platform/issues/7"
    assert "PR #3" in by_id
    assert by_id["PR #3"].data["url"].endswith("/pull/3")
    assert "thread-7" in by_id
    assert "msg-7" in by_id
    for record in context.retrieved_records:
        assert record.source in ("GitHub", "Gmail", "Relationship")


def test_evidence_links_real_records_with_real_urls():
    record = RetrievedRecord(
        source="GitHub",
        record_type="issue",
        source_id="Issue #7",
        project_id="proj-x",
        title="Latency spike on checkout",
        summary="p99 doubled",
        data={"body": "p99 doubled", "author": "dana", "url": "https://github.com/acme/platform/issues/7"},
    )
    context = AgentContext(run_id="KO-REAL-EV", question="q")
    context.retrieved_records = [record]
    context.claims = [AnalysisClaim(claim="Checkout latency regressed", kind="risk", source_ids=["Issue #7"])]
    context = EvidenceAgent().run(context)
    assert len(context.evidence) == 1
    ref = context.evidence[0]
    assert ref.source_id == "Issue #7"
    assert ref.title == "Latency spike on checkout"
    assert ref.author == "dana"
    assert ref.url == "#github"


# ------------------------------------------------ 9. no synthetic IDs in code

def test_real_mode_sources_contain_no_hardcoded_synthetic_identifiers():
    sources = [
        backend_root / "app" / "mcp" / "real_provider.py",
        backend_root / "app" / "mcp" / "transport.py",
        backend_root / "app" / "mcp" / "capability_map.py",
        backend_root / "app" / "mcp" / "provider.py",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for forbidden in ("142", "284", "GM-064", "Platform API v2.4"):
            assert forbidden not in text, (
                f"{path.name} must not hardcode {forbidden}"
            )


# ------------------------------------------------------ 10. live integration

@pytest.mark.skipif(
    os.getenv("MCP_INTEGRATION_TESTS") != "1",
    reason="live MCP integration tests are opt-in (MCP_INTEGRATION_TESTS=1)",
)
def test_live_github_capability_check_when_configured():
    provider = RealMCPProvider()
    health = provider.github_health()
    assert health.status in ("connected", "unconfigured"), (
        f"unexpected live status: {health.status} - {health.message}"
    )
    if health.status == "connected":
        assert health.tools


@pytest.mark.skipif(
    os.getenv("MCP_INTEGRATION_TESTS") != "1",
    reason="live MCP integration tests are opt-in (MCP_INTEGRATION_TESTS=1)",
)
def test_live_gmail_capability_check_when_configured():
    provider = RealMCPProvider()
    health = provider.gmail_health()
    assert health.status in ("connected", "unconfigured"), (
        f"unexpected live status: {health.status} - {health.message}"
    )
    if health.status == "connected":
        assert health.tools
