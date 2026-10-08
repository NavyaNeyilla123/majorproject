"""Health and status helpers for MCP servers (mock dataset and real servers).

Honesty contract:
- mock provider: reports mock_connected against the synthetic dataset.
- real provider: reports connected only after a live capability check
  (tools/list) succeeded; otherwise unconfigured/unavailable/error with the
  reason. ``healthy=true`` is only ever produced by an actual check.
"""

from typing import Callable, List, Optional

from app.mcp.github import GITHUB_MCP_ENDPOINT, GITHUB_MCP_TOOLS
from app.mcp.gmail import GMAIL_MCP_ENDPOINT, GMAIL_MCP_TOOLS
from app.mcp.models import MCPHealth, MCPHealthReport, MCPServerStatus, MCPStatusResponse


def dataset_health(
    server: str,
    provider_name: str,
    endpoint: str,
    count_records: Callable[[], int],
) -> MCPHealth:
    """Build an MCPHealth entry by loading the synthetic dataset for one server."""
    try:
        count = count_records()
    except Exception as exc:  # unreadable dataset => unhealthy, never a claim of connectivity
        return MCPHealth(
            server=server,
            provider=provider_name,
            healthy=False,
            mock_connected=False,
            message=f"unable to read the synthetic {server} dataset: {exc}",
            endpoint=endpoint,
            status="error",
        )
    is_mock = provider_name == "mock"
    return MCPHealth(
        server=server,
        provider=provider_name,
        healthy=True,
        mock_connected=is_mock,
        message=f"mock_connected to the synthetic {server} dataset"
        if is_mock
        else f"connected to {server}",
        endpoint=endpoint,
        records_available=count,
        status="mock_connected" if is_mock else "connected",
    )


def build_health_report(provider_name: str, github: MCPHealth, gmail: MCPHealth) -> MCPHealthReport:
    return MCPHealthReport(
        provider=provider_name,
        healthy=github.healthy and gmail.healthy,
        github=github,
        gmail=gmail,
    )


def server_status(server: str, health: MCPHealth) -> MCPServerStatus:
    if health.status:
        status = health.status
    elif health.mock_connected:
        status = "mock_connected"
    elif health.healthy:
        status = "connected"
    else:
        status = "disconnected"
    tools: Optional[List[str]] = health.tools
    if tools is None:
        tools = list(GITHUB_MCP_TOOLS if server == "github" else GMAIL_MCP_TOOLS)
    return MCPServerStatus(
        server=server,
        provider=health.provider,
        status=status,
        healthy=health.healthy,
        endpoint=health.endpoint,
        tools=list(tools),
        message=health.message,
    )


def build_status_response(provider) -> MCPStatusResponse:
    """Compose GET /api/mcp/status for a resolved provider."""
    report = provider.health_check()
    is_mock = provider.provider_name == "mock"
    if is_mock:
        mode = "Mock MCP"
        data_source = "Synthetic Data"
        detail = "Serves the synthetic GitHub + Gmail dataset. No real MCP connectivity."
    else:
        mode = "Real MCP"
        data_source = "Live data"
        detail = (
            "Real MCP mode (read-only adapter). "
            f"GitHub: {report.github.status}; Gmail: {report.gmail.status}. "
            "healthy=true only after a successful live capability check."
        )
    return MCPStatusResponse(
        provider=provider.provider_name,
        mode=mode,
        environment="Development",
        data_source=data_source,
        github=server_status("github", report.github),
        gmail=server_status("gmail", report.gmail),
        detail=detail,
    )
