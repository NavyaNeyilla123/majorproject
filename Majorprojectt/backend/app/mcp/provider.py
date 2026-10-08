"""Provider selection for the MCP seam.

MCP_PROVIDER env var decides which implementation serves MCP tool calls:

- ``mock``  (default): MockMCPProvider over the synthetic JSON dataset.
- ``real``  (opt-in):   RealMCPProvider over configured GitHub/Gmail MCP
  servers (read-only). Unconfigured, unreachable or failing servers surface
  a clear MCPProviderError - there is NO silent fallback to mock data.

Resolution is lazy (called when a provider is needed), so a bad selection
fails at the point of use with a structured error instead of at import time.
"""

import os
from typing import Optional

from app.mcp.base import MCPProvider, MCPProviderError
from app.mcp.mock_provider import mock_provider

DEFAULT_MCP_PROVIDER = "mock"
REAL_PROVIDER = "real"


def resolve_provider_name() -> str:
    name = os.getenv("MCP_PROVIDER", DEFAULT_MCP_PROVIDER).strip().lower()
    return name or DEFAULT_MCP_PROVIDER


def get_mcp_provider(name: Optional[str] = None) -> MCPProvider:
    """Return the configured MCP provider (mock by default, real when selected)."""
    resolved = (name or resolve_provider_name()).strip().lower()
    if resolved == DEFAULT_MCP_PROVIDER:
        return mock_provider
    if resolved == REAL_PROVIDER:
        from app.mcp.real_provider import RealMCPProvider

        return RealMCPProvider()
    raise MCPProviderError(
        f"Unknown MCP_PROVIDER {resolved!r}. Supported providers: "
        f"{DEFAULT_MCP_PROVIDER!r}, {REAL_PROVIDER!r}."
    )
