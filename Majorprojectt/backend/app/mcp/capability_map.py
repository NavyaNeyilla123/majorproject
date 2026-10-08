"""Binds MCPProvider operations to tools discovered from a real MCP server.

No MCP tool name is assumed to exist. Binding always runs against the
server's live ``tools/list`` response: the tables below are matching
heuristics scored over whatever the server actually advertised, and an
operation that matches nothing is reported as an unsupported capability
instead of being faked or silently skipped.

Read-only guarantee: any tool whose name contains a write/action verb is
excluded from binding entirely - including explicit overrides - so this
adapter can never issue create/update/delete/send style calls even when
the server offers them.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Sequence

from app.mcp.base import MCPProviderError
from app.mcp.transport import DiscoveredTool

# Verbs that mark a tool as mutating. Exact token match after splitting the
# tool name on non-alphanumerics ("list_labels" keeps token "labels" and is
# read-only; "label_issue" has token "label" and is excluded).
WRITE_TOKENS: FrozenSet[str] = frozenset(
    {
        "create", "update", "delete", "remove", "write", "push", "merge",
        "revert", "edit", "modify", "archive", "trash", "send", "draft",
        "reply", "post", "approve", "reject", "submit", "fork", "upload",
        "move", "rename", "assign", "close", "reopen", "label", "unlabel",
        "star", "mute", "pin", "ban", "invite", "revoke", "batch", "import",
        "set", "add", "clear", "reset", "trigger", "run", "execute", "start",
        "stop", "enable", "disable", "install", "publish", "deploy",
    }
)

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def tool_tokens(name: str) -> List[str]:
    return [token for token in _TOKEN_SPLIT_RE.split(name.lower()) if token]


def is_readonly_tool(name: str) -> bool:
    """True when no write/action verb appears in the tool name."""
    return not (set(tool_tokens(name)) & WRITE_TOKENS)


@dataclass(frozen=True)
class OperationSpec:
    """At least one domain token AND one action token must match."""

    domain: FrozenSet[str]
    action: FrozenSet[str]


def _spec(domain: Sequence[str], action: Sequence[str]) -> OperationSpec:
    return OperationSpec(frozenset(domain), frozenset(action))


# Keys are stable operation identifiers: "<verb>.<target>".
# These are NOT server tool names - resolution happens against the live list.
OPERATION_SPECS: Dict[str, OperationSpec] = {
    "search.repositories": _spec(
        ("repo", "repos", "repository", "repositories"),
        ("search", "list", "find", "query"),
    ),
    "search.issues": _spec(
        ("issue", "issues"),
        ("search", "list", "find", "query"),
    ),
    "search.pull_requests": _spec(
        ("pull", "pulls", "pr", "prs"),
        ("search", "list", "find", "query"),
    ),
    "search.commits": _spec(
        ("commit", "commits"),
        ("search", "list", "find", "query", "get"),
    ),
    "search.reviews": _spec(
        ("review", "reviews"),
        ("search", "list", "find", "query"),
    ),
    "get.repository": _spec(
        ("repo", "repos", "repository", "repositories"),
        ("get", "read", "fetch", "show", "info", "describe"),
    ),
    "get.issue": _spec(
        ("issue", "issues"),
        ("get", "read", "fetch", "show"),
    ),
    "get.pull_request": _spec(
        ("pull", "pulls", "pr", "prs"),
        ("get", "read", "fetch", "show"),
    ),
    "get.commit": _spec(
        ("commit", "commits"),
        ("get", "read", "fetch", "show"),
    ),
    "get.review": _spec(
        ("review", "reviews"),
        ("get", "read", "fetch", "show"),
    ),
    "search.threads": _spec(
        ("thread", "threads"),
        ("search", "list", "find", "query"),
    ),
    "search.messages": _spec(
        ("message", "messages", "email", "emails", "mail"),
        ("search", "list", "find", "query"),
    ),
    "get.thread": _spec(
        ("thread", "threads"),
        ("get", "read", "fetch", "show"),
    ),
    "get.message": _spec(
        ("message", "messages", "email", "emails", "mail"),
        ("get", "read", "fetch", "show"),
    ),
}


def load_overrides(server: str) -> Dict[str, str]:
    """Optional explicit operation->tool map (MCP_<SERVER>_MAP JSON object)."""
    raw = os.getenv(f"MCP_{server.upper()}_MAP", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MCPProviderError(
            f"MCP_{server.upper()}_MAP is not a valid JSON object: {exc.msg}"
        ) from None
    if not isinstance(parsed, dict):
        raise MCPProviderError(
            f"MCP_{server.upper()}_MAP must be a JSON object mapping "
            f"operation keys to tool names"
        )
    return {str(key): str(value) for key, value in parsed.items()}


def resolve_tool(
    op_key: str,
    tools: Sequence[DiscoveredTool],
    overrides: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Pick the discovered tool for one operation, or None when unsupported.

    Overrides are honoured only when they name a tool the server actually
    advertised and that tool is read-only; both violations raise.
    """
    overrides = overrides or {}
    if op_key in overrides:
        wanted = overrides[op_key]
        available = {tool.name for tool in tools}
        if wanted not in available:
            raise MCPProviderError(
                f"override MCP map names tool {wanted!r} for {op_key!r}, but the "
                f"server does not advertise it (discovered: "
                f"{', '.join(sorted(available)) or 'none'})"
            )
        if not is_readonly_tool(wanted):
            raise MCPProviderError(
                f"refusing to bind {op_key!r} to write tool {wanted!r}: "
                f"the adapter is read-only"
            )
        return wanted

    spec = OPERATION_SPECS.get(op_key)
    if spec is None:
        return None

    best: Optional[tuple] = None
    best_name: Optional[str] = None
    for tool in tools:
        if not is_readonly_tool(tool.name):
            continue
        tokens = set(tool_tokens(tool.name))
        domain_hits = len(tokens & spec.domain)
        action_hits = len(tokens & spec.action)
        if not domain_hits or not action_hits:
            continue
        score = (domain_hits, action_hits, -len(tool.name), tool.name)
        if best is None or score > best:
            best = score
            best_name = tool.name
    return best_name


def resolve_or_raise(
    server: str,
    op_key: str,
    tools: Sequence[DiscoveredTool],
    overrides: Optional[Dict[str, str]] = None,
) -> str:
    """Resolve an operation or raise a clear unsupported-capability error."""
    name = resolve_tool(op_key, tools, overrides)
    if name:
        return name
    available = ", ".join(tool.name for tool in tools) or "none"
    raise MCPProviderError(
        f"{server} MCP server exposes no read-only tool for {op_key!r} "
        f"(discovered tools: {available}); configure MCP_{server.upper()}_MAP "
        f"if the server names this capability differently"
    )


def find_tool(name: str, tools: Sequence[DiscoveredTool]) -> DiscoveredTool:
    for tool in tools:
        if tool.name == name:
            return tool
    raise MCPProviderError(f"tool {name!r} disappeared from the discovered tool list")
