import sys
from pathlib import Path

import pytest

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient

from app.main import app
from app.agents.models import AgentContext
from app.agents.planner_agent import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.mcp import (
    MCPProviderError,
    MockMCPProvider,
    get_mcp_provider,
    mock_provider,
)
from app.mcp.real_provider import RealMCPProvider

client = TestClient(app)

CRITICAL_QUESTION = "What could delay the Platform API v2.4 release, and what should we do next?"

MOCK_PROVIDER_SOURCE = (backend_root / "app" / "mcp" / "mock_provider.py").read_text(
    encoding="utf-8"
)


# ------------------------------------------------------- 1. Provider selection

def test_default_provider_is_mock(monkeypatch):
    monkeypatch.delenv("MCP_PROVIDER", raising=False)
    provider = get_mcp_provider()
    assert isinstance(provider, MockMCPProvider)
    assert provider is mock_provider
    assert provider.provider_name == "mock"


def test_real_provider_selected_without_mock_fallback(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "real")
    for key in (
        "MCP_GITHUB_URL", "MCP_GITHUB_COMMAND",
        "MCP_GMAIL_URL", "MCP_GMAIL_COMMAND",
    ):
        monkeypatch.delenv(key, raising=False)
    provider = get_mcp_provider()
    assert isinstance(provider, RealMCPProvider)
    assert not isinstance(provider, MockMCPProvider)
    assert provider.provider_name == "real"
    with pytest.raises(MCPProviderError) as excinfo:
        provider.search_github(kind="issues")
    assert "unconfigured" in str(excinfo.value)


def test_unknown_provider_raises_clear_error(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "banana")
    with pytest.raises(MCPProviderError) as excinfo:
        get_mcp_provider()
    assert "banana" in str(excinfo.value)


def test_empty_provider_env_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "   ")
    assert get_mcp_provider().provider_name == "mock"


# ------------------------------------------------- 2. MockMCPProvider behavior

def test_mock_provider_serves_github_records_dynamically():
    provider = get_mcp_provider()
    issues = provider.search_github(project_id="proj-platform-api", kind="issues")
    assert issues, "expected issues for the demo project"
    first_number = issues[0].data["number"]
    fetched = provider.get_github_issue(first_number)
    assert fetched is not None
    assert fetched.data["number"] == first_number
    assert fetched.source_id == f"Issue #{first_number}"
    assert provider.get_github_issue(999999) is None

    prs = provider.search_github(project_id="proj-platform-api", kind="pull_requests")
    assert prs
    fetched_pr = provider.get_github_pull_request(prs[0].data["number"])
    assert fetched_pr is not None and fetched_pr.record_type == "pull_request"

    repos = provider.search_github(project_id="proj-platform-api", kind="repositories")
    assert repos
    fetched_repo = provider.get_github_repository(repos[0].source_id)
    assert fetched_repo is not None and fetched_repo.record_type == "repository"


def test_mock_provider_serves_gmail_records_dynamically():
    provider = get_mcp_provider()
    threads = provider.search_gmail(project_id="proj-platform-api", kind="threads")
    assert threads, "expected threads for the demo project"
    first_id = threads[0].source_id
    fetched = provider.get_gmail_thread(first_id)
    assert fetched is not None and fetched.data["id"] == first_id
    assert provider.get_gmail_thread("GM-DOES-NOT-EXIST") is None

    messages = provider.search_gmail(kind="messages", thread_id=first_id)
    assert messages
    assert all(m.data["thread_id"] == first_id for m in messages)
    fetched_message = provider.get_gmail_message(messages[0].source_id)
    assert fetched_message is not None


def test_mock_provider_serves_cross_source_links():
    provider = get_mcp_provider()
    links = provider.get_cross_source_links("proj-platform-api")
    assert links
    assert all(l.record_type == "cross_source_link" for l in links)
    assert all(l.source == "Relationship" for l in links)


def test_mock_provider_search_filters_and_kind_validation():
    provider = get_mcp_provider()
    all_project_issues = provider.search_github(project_id="proj-platform-api", kind="issues")
    limited = provider.search_github(project_id="proj-platform-api", kind="issues", limit=2)
    assert len(limited) == min(2, len(all_project_issues))

    other_project = provider.search_github(project_id="proj-other", kind="issues")
    assert other_project == []

    with pytest.raises(MCPProviderError):
        provider.search_github(kind="gists")
    with pytest.raises(MCPProviderError):
        provider.search_gmail(kind="labels")


def test_mock_provider_source_contains_no_hardcoded_record_ids():
    for hardcoded in ("142", "284", "GM-064"):
        assert hardcoded not in MOCK_PROVIDER_SOURCE, (
            f"provider code must not hardcode {hardcoded}; look it up from the dataset"
        )


def test_mock_provider_reports_healthy_mock_status():
    report = get_mcp_provider().health_check()
    assert report.provider == "mock"
    assert report.healthy is True
    assert report.github.mock_connected is True and report.github.healthy is True
    assert report.gmail.mock_connected is True and report.gmail.healthy is True
    assert report.github.records_available and report.github.records_available > 0
    assert report.gmail.records_available and report.gmail.records_available > 0


# --------------------------------------------------- 3. GET /api/mcp/status

def test_mcp_status_endpoint_reports_mock_provider():
    response = client.get("/api/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["mode"] == "Mock MCP"
    assert data["environment"] == "Development"
    assert data["data_source"] == "Synthetic Data"
    for server in ("github", "gmail"):
        assert data[server]["status"] == "mock_connected"
        assert data[server]["healthy"] is True
        assert data[server]["provider"] == "mock"
        assert data[server]["tools"]
        assert data[server]["endpoint"].startswith("mcp://")
    assert "No real MCP connectivity" in data["detail"]


def test_mcp_status_endpoint_real_reports_honestly_without_fallback(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "real")
    for key in (
        "MCP_GITHUB_URL", "MCP_GITHUB_COMMAND",
        "MCP_GMAIL_URL", "MCP_GMAIL_COMMAND",
    ):
        monkeypatch.delenv(key, raising=False)
    response = client.get("/api/mcp/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "real"
    assert data["mode"] == "Real MCP"
    assert data["data_source"] == "Live data"
    for server in ("github", "gmail"):
        assert data[server]["status"] == "unconfigured"
        assert data[server]["healthy"] is False
        assert data[server]["provider"] == "real"
        assert data[server]["tools"] == []
        assert data[server]["endpoint"] == ""
        assert "not configured" in data[server]["message"]
    assert "mock_connected" not in str(data)
    assert "capability check" in data["detail"]


def test_mcp_status_endpoint_unknown_provider_returns_error(monkeypatch):
    monkeypatch.setenv("MCP_PROVIDER", "banana")
    response = client.get("/api/mcp/status")
    assert response.status_code == 500
    assert "banana" in response.json()["detail"]


# ------------------------------------------- 4. Retrieval through the MCP seam

def test_retrieval_agent_default_uses_mock_mcp_provider():
    agent = RetrievalAgent()
    context = PlannerAgent().run(AgentContext(run_id="KO-MCP001", question=CRITICAL_QUESTION))
    agent.run(context)
    assert isinstance(agent.provider, MockMCPProvider)


def test_retrieval_records_flow_through_mcp_provider():
    agent = RetrievalAgent()
    context = PlannerAgent().run(AgentContext(run_id="KO-MCP002", question=CRITICAL_QUESTION))
    context = agent.run(context)
    source_ids = {r.source_id for r in context.retrieved_records}
    assert "Issue #142" in source_ids
    assert "PR #284" in source_ids
    assert "GM-064" in source_ids
    for record in context.retrieved_records:
        assert record.project_id == "proj-platform-api"
        assert record.source in ("GitHub", "Gmail", "Relationship")
