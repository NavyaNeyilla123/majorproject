from fastapi import APIRouter, HTTPException

from app.mcp import (
    MCPProviderError,
    MCPProviderNotImplementedError,
    MCPStatusResponse,
    build_status_response,
    get_mcp_provider,
)

router = APIRouter()


@router.get("/mcp/status", response_model=MCPStatusResponse)
def get_mcp_status() -> MCPStatusResponse:
    """Report which MCP provider is active and whether each source is usable.

    Mock provider: reports mock_connected against the synthetic dataset.
    Real provider: performs an actual capability check per server and reports
    connected / unconfigured / unavailable / error honestly - healthy=true is
    only ever set after a successful live tools/list round-trip. An unknown
    MCP_PROVIDER returns 500; there is no silent fallback to mock.
    """
    try:
        provider = get_mcp_provider()
    except MCPProviderNotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except MCPProviderError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return build_status_response(provider)
