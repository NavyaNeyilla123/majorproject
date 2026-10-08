"""GitHub MCP server contract: endpoint, tool registry, search kinds.

No network traffic happens for these names while the mock provider is active;
they document the tool surface a real GitHub MCP server must expose.
"""

GITHUB_MCP_ENDPOINT = "mcp://github/acme-eng"

GITHUB_MCP_TOOLS = [
    "search_github",
    "get_github_repository",
    "get_github_issue",
    "get_github_pull_request",
    "get_github_commit",
    "get_github_review",
]

GITHUB_SEARCH_KINDS = ("repositories", "issues", "pull_requests", "commits", "reviews")
