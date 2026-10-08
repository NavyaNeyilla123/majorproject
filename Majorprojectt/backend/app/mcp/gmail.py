"""Gmail MCP server contract: endpoint, tool registry, search kinds.

No network traffic happens for these names while the mock provider is active;
they document the tool surface a real Gmail MCP server must expose.
"""

GMAIL_MCP_ENDPOINT = "mcp://gmail/project-inbox"

GMAIL_MCP_TOOLS = [
    "search_gmail",
    "get_gmail_thread",
    "get_gmail_message",
]

GMAIL_SEARCH_KINDS = ("threads", "messages")
