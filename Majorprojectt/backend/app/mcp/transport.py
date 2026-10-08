"""Real MCP transport (Step 10): connection lifecycle and tool discovery.

Speaks the Model Context Protocol through the official Python ``mcp`` SDK
client (stdio subprocess and streamable HTTP). A connection is opened for a
single operation and closed afterwards; nothing is kept alive between calls.

Honesty rules enforced here:
- ``connected``/``healthy`` is reported only after a successful live
  ``tools/list`` round-trip against the configured server. Unconfigured,
  unreachable and failing servers are reported as such - never as connected.
- No tool name is assumed to exist: callers bind operations against the
  tools the server actually advertised (see app.mcp.capability_map).
- A tool is only ever called when it was present in the discovered list.

Security rules enforced here:
- Credentials are read from the environment only, never from source code.
- Credential values are never logged, never returned to API callers, and are
  redacted from any error text that could otherwise leak them.
"""

import asyncio
import json
import os
import re
import shlex
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncContextManager, Callable, Dict, List, Optional, Sequence

from app.mcp.base import MCPProviderError

DEFAULT_CONNECT_TIMEOUT_MS = 10_000
DEFAULT_CALL_TIMEOUT_MS = 15_000

STATE_CONNECTED = "connected"
STATE_UNCONFIGURED = "unconfigured"
STATE_UNAVAILABLE = "unavailable"
STATE_ERROR = "error"

_MESSAGE_LIMIT = 400

_BEARER_RE = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
_SECRETISH_RE = re.compile(
    r"(?i)(token|authorization|password|secret|api[_-]?key)([\"'=:\s]+)[^\s\"',;]+"
)


class ConnectionFailed(Exception):
    """Internal: a connection/call attempt failed, with a status state."""

    def __init__(self, state: str, message: str) -> None:
        super().__init__(message)
        self.state = state
        self.message = message


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _timeout_ms(env_name: str, default_ms: int) -> int:
    raw = _env(env_name)
    if not raw:
        return default_ms
    try:
        value = int(raw)
    except ValueError:
        return default_ms
    return value if value > 0 else default_ms


def _parse_args(raw: str) -> List[str]:
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def _parse_headers(raw: str) -> Dict[str, str]:
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}
    return {}


def redact(text: str, *secrets: str) -> str:
    """Remove credential material from a message before it leaves transport."""
    if not text:
        return ""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    text = _BEARER_RE.sub(r"\1[redacted]", text)
    text = _SECRETISH_RE.sub(r"\1\2[redacted]", text)
    if len(text) > _MESSAGE_LIMIT:
        text = text[:_MESSAGE_LIMIT] + "..."
    return text


DEFAULT_TOKEN_ENV: Dict[str, str] = {
    "github": "GITHUB_PERSONAL_ACCESS_TOKEN",
    "gmail": "",
}


@dataclass(frozen=True)
class MCPServerConfig:
    """Resolved (secret-safe) configuration for one MCP server."""

    server: str
    transport: str = ""
    url: str = ""
    command: str = ""
    args: Sequence[str] = ()
    headers: Dict[str, str] = field(default_factory=dict)
    token: str = field(default="", repr=False)
    token_env: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.transport)

    @property
    def endpoint(self) -> str:
        if self.url:
            return self.url
        if self.command:
            return " ".join([self.command, *self.args]).strip()
        return ""


def load_server_config(server: str) -> MCPServerConfig:
    """Read one server's connection settings from the environment."""
    prefix = f"MCP_{server.upper()}"
    url = _env(f"{prefix}_URL")
    command = _env(f"{prefix}_COMMAND")
    token = _env(f"{prefix}_TOKEN")
    token_env = _env(f"{prefix}_TOKEN_ENV") or DEFAULT_TOKEN_ENV.get(server, "")
    if url:
        transport = "streamable_http"
    elif command:
        transport = "stdio"
    else:
        transport = ""
    return MCPServerConfig(
        server=server,
        transport=transport,
        url=url,
        command=command,
        args=tuple(_parse_args(_env(f"{prefix}_ARGS"))),
        headers=_parse_headers(_env(f"{prefix}_HEADERS")),
        token=token,
        token_env=token_env,
    )


@dataclass(frozen=True)
class DiscoveredTool:
    """A tool the server actually advertised via tools/list."""

    name: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionOutcome:
    state: str
    message: str
    tools: List[DiscoveredTool] = field(default_factory=list)

    @property
    def tool_names(self) -> List[str]:
        return [tool.name for tool in self.tools]


def _extract_tools(listed: Any) -> List[DiscoveredTool]:
    raw = getattr(listed, "tools", None)
    if raw is None and isinstance(listed, dict):
        raw = listed.get("tools")
    if raw is None:
        raise MCPProviderError("malformed tools/list response: missing 'tools'")
    tools: List[DiscoveredTool] = []
    for item in raw:
        if isinstance(item, dict):
            name, schema = item.get("name"), item.get("inputSchema") or {}
        else:
            name = getattr(item, "name", None)
            schema = getattr(item, "inputSchema", None) or {}
        if not name:
            continue
        tools.append(
            DiscoveredTool(name=str(name), input_schema=schema if isinstance(schema, dict) else {})
        )
    return tools


def _extract_payload(result: Any, tool_name: str, server: str, secret: str) -> Any:
    is_error = bool(getattr(result, "isError", False))
    if isinstance(result, dict):
        is_error = bool(result.get("isError"))
    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    texts: List[str] = []
    for part in content or []:
        text = getattr(part, "text", None)
        if text is None and isinstance(part, dict):
            text = part.get("text")
        if text:
            texts.append(str(text))
    structured = getattr(result, "structuredContent", None)
    if structured is None and isinstance(result, dict):
        structured = result.get("structuredContent")

    if is_error:
        detail = redact("\n".join(texts) or "tool reported an error", secret)
        raise MCPProviderError(f"{server} tool {tool_name!r} failed: {detail}")

    if structured is not None:
        return structured
    joined = "\n".join(texts).strip()
    if not joined:
        return None
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        pass
    parsed: List[Any] = []
    for text in texts:
        try:
            parsed.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    if len(parsed) == 1:
        return parsed[0]
    if parsed:
        return parsed
    return joined


SessionFactory = Callable[[MCPServerConfig], AsyncContextManager[Any]]


def _stdio_session(cfg: MCPServerConfig) -> AsyncContextManager[Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env: Dict[str, str] = {}
    if cfg.token and cfg.token_env:
        env[cfg.token_env] = cfg.token

    @asynccontextmanager
    async def open_session():
        params = StdioServerParameters(
            command=cfg.command,
            args=list(cfg.args),
            env=env or None,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    return open_session()


def _streamable_http_session(cfg: MCPServerConfig) -> AsyncContextManager[Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = dict(cfg.headers)
    has_auth = any(key.lower() == "authorization" for key in headers)
    if cfg.token and not has_auth:
        headers["Authorization"] = f"Bearer {cfg.token}"
    timeout_s = _timeout_ms("MCP_CONNECT_TIMEOUT_MS", DEFAULT_CONNECT_TIMEOUT_MS) / 1000

    @asynccontextmanager
    async def open_session():
        async with streamablehttp_client(
            cfg.url,
            headers=headers or None,
            timeout=timeout_s,
        ) as (read, write, _session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    return open_session()


def default_session_factory(cfg: MCPServerConfig) -> AsyncContextManager[Any]:
    if cfg.transport == "streamable_http":
        return _streamable_http_session(cfg)
    if cfg.transport == "stdio":
        return _stdio_session(cfg)
    raise MCPProviderError(
        f"{cfg.server}: no MCP transport configured "
        f"(set MCP_{cfg.server.upper()}_COMMAND or MCP_{cfg.server.upper()}_URL)"
    )


class MCPConnection:
    """One MCP server connection: discover -> bind -> call, all read-only.

    ``config`` is loaded from the environment on every entry point, so a
    configuration change takes effect without restarting the process. Tests
    inject an explicit ``config`` plus a fake ``session_factory`` to exercise
    every path without spawning a process or touching the network.
    """

    def __init__(
        self,
        server: str,
        config: Optional[MCPServerConfig] = None,
        session_factory: Optional[SessionFactory] = None,
    ) -> None:
        self.server = server
        self._explicit_config = config
        self._session_factory = session_factory
        self._tools: Optional[List[DiscoveredTool]] = None

    @property
    def config(self) -> MCPServerConfig:
        cfg = self._explicit_config if self._explicit_config is not None else load_server_config(self.server)
        if not self._same_config(cfg):
            self._tools = None
            self._loaded_key = self._key(cfg)
        return cfg

    _loaded_key: Optional[Any] = None

    @staticmethod
    def _key(cfg: MCPServerConfig) -> tuple:
        return (
            cfg.transport,
            cfg.url,
            cfg.command,
            tuple(cfg.args),
            tuple(sorted(cfg.headers.items())),
            bool(cfg.token),
            cfg.token_env,
        )

    def _same_config(self, cfg: MCPServerConfig) -> bool:
        return self._loaded_key == self._key(cfg)

    def endpoint_display(self) -> str:
        return self.config.endpoint

    def discover(self) -> ConnectionOutcome:
        """Perform a live capability check (tools/list). Never raises."""
        cfg = self.config
        if not cfg.configured:
            prefix = f"MCP_{self.server.upper()}"
            return ConnectionOutcome(
                STATE_UNCONFIGURED,
                f"{self.server} MCP server is not configured; set {prefix}_COMMAND "
                f"(stdio) or {prefix}_URL (streamable HTTP)",
            )
        timeout_ms = _timeout_ms("MCP_CONNECT_TIMEOUT_MS", DEFAULT_CONNECT_TIMEOUT_MS)
        try:
            tools = self._run(self._discover_once(cfg), timeout_ms, cfg)
        except ConnectionFailed as exc:
            return ConnectionOutcome(exc.state, exc.message)
        self._tools = tools
        return ConnectionOutcome(
            STATE_CONNECTED,
            f"connected to {self.server} MCP server; {len(tools)} tool(s) discovered "
            f"(read-only adapter)",
            tools=tools,
        )

    def require_tools(self) -> List[DiscoveredTool]:
        """Cached discovery when available, else a live check. Never a fallback."""
        if self._tools is not None:
            return self._tools
        outcome = self.discover()
        if outcome.state != STATE_CONNECTED:
            raise MCPProviderError(
                f"{self.server} MCP server {outcome.state}: {outcome.message}"
            )
        return outcome.tools

    def call(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Invoke one discovered tool. Raises MCPProviderError on any failure."""
        cfg = self.config
        if not cfg.configured:
            outcome = self.discover()
            raise MCPProviderError(
                f"{self.server} MCP server {outcome.state}: {outcome.message}"
            )
        if self._tools is None:
            self.require_tools()
        timeout_ms = _timeout_ms("MCP_CALL_TIMEOUT_MS", DEFAULT_CALL_TIMEOUT_MS)
        try:
            return self._run(self._call_once(cfg, tool_name, arguments), timeout_ms, cfg)
        except ConnectionFailed as exc:
            raise MCPProviderError(
                f"{self.server} tool {tool_name!r} failed ({exc.state}): {exc.message}"
            ) from None

    # ------------------------------------------------------------------ async

    async def _discover_once(self, cfg: MCPServerConfig) -> List[DiscoveredTool]:
        factory = self._session_factory or default_session_factory(cfg)
        async with factory(cfg) as session:
            listed = await session.list_tools()
            return _extract_tools(listed)

    async def _call_once(
        self,
        cfg: MCPServerConfig,
        tool_name: str,
        arguments: Optional[Dict[str, Any]],
    ) -> Any:
        factory = self._session_factory or default_session_factory(cfg)
        async with factory(cfg) as session:
            if self._tools is None:
                self._tools = _extract_tools(await session.list_tools())
            known = {tool.name for tool in self._tools}
            if tool_name not in known:
                raise MCPProviderError(
                    f"{self.server} MCP server does not expose tool {tool_name!r} "
                    f"(discovered: {', '.join(sorted(known)) or 'none'})"
                )
            result = await session.call_tool(tool_name, arguments or {})
            return _extract_payload(result, tool_name, self.server, cfg.token)

    def _run(self, coro: Any, timeout_ms: int, cfg: MCPServerConfig) -> Any:
        return _run_connection(coro, timeout_ms, cfg)


def _run_connection(coro: Any, timeout_ms: int, cfg: MCPServerConfig) -> Any:
    """Run one async MCP operation on a private event loop, mapped to states."""

    async def guarded() -> Any:
        return await asyncio.wait_for(coro, timeout_ms / 1000)

    wrapped = guarded()
    try:
        return asyncio.run(wrapped)
    except (asyncio.TimeoutError, TimeoutError):
        wrapped.close()
        raise ConnectionFailed(
            STATE_UNAVAILABLE,
            f"timed out after {timeout_ms}ms waiting for the {cfg.server} MCP server",
        )
    except ConnectionFailed:
        wrapped.close()
        raise
    except MCPProviderError as exc:
        wrapped.close()
        raise ConnectionFailed(STATE_ERROR, redact(str(exc), cfg.token))
    except OSError as exc:
        wrapped.close()
        detail = redact(str(exc) or exc.__class__.__name__, cfg.token)
        raise ConnectionFailed(
            STATE_UNAVAILABLE,
            f"could not reach the {cfg.server} MCP server: {detail}",
        )
    except RuntimeError as exc:
        wrapped.close()
        detail = redact(str(exc), cfg.token)
        raise ConnectionFailed(STATE_ERROR, f"MCP client runtime error: {detail}")
    except Exception as exc:  # noqa: BLE001 - status must classify everything
        wrapped.close()
        detail = redact(str(exc) or exc.__class__.__name__, cfg.token)
        raise ConnectionFailed(
            STATE_ERROR, f"{exc.__class__.__name__}: {detail}"
        )
