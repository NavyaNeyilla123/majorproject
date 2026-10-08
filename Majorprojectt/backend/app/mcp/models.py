from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPRecord(BaseModel):
    """One record returned through the MCP provider seam.

    source_mode marks provenance: "mock" for synthetic dataset records,
    "real" for records normalized from a live MCP server. Both providers
    emit the same shape; consumers never branch on the mode.
    """

    source: str
    record_type: str
    source_id: str
    project_id: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    relationships: Dict[str, Any] = Field(default_factory=dict)
    source_mode: str = "mock"


class MCPHealth(BaseModel):
    server: str
    provider: str = "mock"
    healthy: bool = False
    mock_connected: bool = False
    message: str = ""
    endpoint: str = ""
    records_available: Optional[int] = None
    status: str = ""
    tools: Optional[List[str]] = None


class MCPHealthReport(BaseModel):
    provider: str
    healthy: bool = False
    github: MCPHealth
    gmail: MCPHealth


class MCPServerStatus(BaseModel):
    server: str
    provider: str = "mock"
    status: str = "disconnected"
    healthy: bool = False
    endpoint: str = ""
    tools: List[str] = Field(default_factory=list)
    message: str = ""


class MCPStatusResponse(BaseModel):
    provider: str
    mode: str
    environment: str
    data_source: str
    github: MCPServerStatus
    gmail: MCPServerStatus
    detail: str = ""
