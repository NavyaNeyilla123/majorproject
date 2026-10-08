"""RealMCPProvider (Step 10): MCPProvider over live GitHub/Gmail MCP servers.

Selected with ``MCP_PROVIDER=real``. Each operation resolves its capability
against the server's live ``tools/list`` response (never an assumed tool
name), calls exactly one discovered read-only tool, and normalizes the raw
payload into the same MCPRecord shape the mock provider emits - preserving
real IDs, numbers and URLs, and omitting any field the server did not
provide (nothing is fabricated).

There is no fallback of any kind: an unconfigured, unreachable or failing
server raises MCPProviderError with an honest message instead of serving
mock data.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.mcp.base import MCPProvider, MCPProviderError
from app.mcp.capability_map import (
    find_tool,
    load_overrides,
    resolve_or_raise,
)
from app.mcp.github import GITHUB_SEARCH_KINDS
from app.mcp.gmail import GMAIL_SEARCH_KINDS
from app.mcp.health import build_health_report
from app.mcp.models import MCPHealth, MCPHealthReport, MCPRecord
from app.mcp.transport import (
    STATE_CONNECTED,
    DiscoveredTool,
    MCPConnection,
)

LIST_PAYLOAD_KEYS = (
    "items", "results", "issues", "pull_requests", "commits", "reviews",
    "repositories", "messages", "threads", "emails", "entries", "values", "data",
)

NOT_FOUND_MARKERS = (
    "not found", "notfound", "does not exist", "doesn't exist", "not exist",
    "no such", "404", "unknown issue", "unknown pull", "unknown thread",
    "unknown message", "no matching", "wasn't found", "no results for",
)

_ALIASES: Dict[str, str] = {
    "q": "query",
    "search": "query",
    "search_query": "query",
    "searchquery": "query",
    "keywords": "query",
    "keyword": "query",
    "terms": "query",
    "term": "query",
    "issue_number": "number",
    "issuenumber": "number",
    "pull_number": "number",
    "pr_number": "number",
    "prnumber": "number",
    "pullrequestnumber": "number",
    "thread": "thread_id",
    "tid": "thread_id",
    "threadid": "thread_id",
    "msg_id": "message_id",
    "msgid": "message_id",
    "messageid": "message_id",
    "commit_sha": "sha",
    "commitsha": "sha",
    "per_page": "limit",
    "perpage": "limit",
    "max_results": "limit",
    "maxresults": "limit",
    "max_items": "limit",
    "top": "limit",
    "top_k": "limit",
    "count": "limit",
    "userid": "user_id",
}


def _put(data: Dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return
    if isinstance(value, (list, dict)) and not value:
        return
    data[key] = value


def _first(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def _login(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("login")
            or value.get("username")
            or value.get("name")
            or value.get("email")
            or ""
        )
    if isinstance(value, str):
        return value
    return ""


def _as_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise MCPProviderError(f"malformed payload: {label} is not an integer ({value!r})") from None


def _labels(value: Any) -> List[str]:
    out: List[str] = []
    for item in value or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("label") or ""
            if name:
                out.append(str(name))
        elif item:
            out.append(str(item))
    return out


def _split_owner_repo(repository: str) -> tuple:
    if "/" in repository:
        owner, _, repo = repository.partition("/")
        return owner.strip(), repo.strip()
    return "", repository.strip()


def _repository_from_url(url: str) -> str:
    from urllib.parse import urlsplit

    parts = [seg for seg in urlsplit(url).path.split("/") if seg]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        try:
            ts = float(value)
            if ts > 1e11:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return str(value)
    return str(value)


def _message_headers(message: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for source in (message, message.get("payload") or {}):
        headers = source.get("headers") or []
        for header in headers:
            if isinstance(header, dict) and header.get("name"):
                out[str(header["name"]).lower()] = str(header.get("value") or "")
    for key in ("from", "to", "subject", "cc"):
        if isinstance(message.get(key), str) and message.get(key):
            out.setdefault(key, message[key])
        recipients = message.get("recipients")
        if key == "to" and isinstance(recipients, list) and recipients:
            out.setdefault("to", ", ".join(str(item) for item in recipients))
    return out


def _split_addresses(value: str) -> List[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _sender_email(sender: str) -> str:
    if "<" in sender and ">" in sender:
        inner = sender.split("<", 1)[1].split(">", 1)[0].strip()
        return inner
    return sender if "@" in sender else ""


def _as_list(payload: Any, context: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = None
        for key in LIST_PAYLOAD_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        if items is None:
            items = [payload]
    else:
        raise MCPProviderError(
            f"malformed {context} response: expected list or object, "
            f"got {type(payload).__name__}"
        )
    for item in items:
        if not isinstance(item, dict):
            raise MCPProviderError(
                f"malformed {context} response: record is {type(item).__name__}, expected object"
            )
    return items


def _as_object(payload: Any, context: str) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    if isinstance(payload, dict):
        if not payload:
            return None
        return payload
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]
    raise MCPProviderError(
        f"malformed {context} response: expected object, got {type(payload).__name__}"
    )


class RealMCPProvider(MCPProvider):
    """Read-only MCPProvider backed by configured GitHub/Gmail MCP servers."""

    provider_name = "real"

    def __init__(
        self,
        github: Optional[MCPConnection] = None,
        gmail: Optional[MCPConnection] = None,
    ) -> None:
        self._github_conn = github or MCPConnection("github")
        self._gmail_conn = gmail or MCPConnection("gmail")

    # ------------------------------------------------------------ capabilities

    def _resolve(self, conn: MCPConnection, op_key: str) -> DiscoveredTool:
        tools = conn.require_tools()
        overrides = load_overrides(conn.server)
        name = resolve_or_raise(conn.server, op_key, tools, overrides)
        return find_tool(name, tools)

    @staticmethod
    def _scoping_values(server: str) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        owner = os.getenv(f"MCP_{server.upper()}_OWNER", "").strip()
        repo = os.getenv(f"MCP_{server.upper()}_REPO", "").strip()
        if owner:
            values["owner"] = owner
        if repo:
            values["repo"] = repo
        if server == "gmail":
            values["user_id"] = os.getenv("MCP_GMAIL_USER_ID", "").strip() or "me"
        return values

    @staticmethod
    def _build_arguments(tool: DiscoveredTool, values: Dict[str, Any], server: str) -> Dict[str, Any]:
        """Schema-driven arguments; required parameters we cannot supply fail clearly."""
        schema = tool.input_schema or {}
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required")
        required = required if isinstance(required, list) else []

        def match(key: str) -> Any:
            if key in values:
                return values[key]
            canonical = _ALIASES.get(key.lower())
            if canonical:
                return values.get(canonical)
            return None

        arguments: Dict[str, Any] = {}
        missing: List[str] = []
        for key in required:
            value = match(key)
            if value is None or value == "":
                missing.append(str(key))
            else:
                arguments[key] = value
        if missing:
            if server == "github":
                hint = "MCP_GITHUB_OWNER/MCP_GITHUB_REPO"
            else:
                hint = "MCP_GMAIL_USER_ID"
            raise MCPProviderError(
                f"tool {tool.name!r} requires parameter(s) {', '.join(missing)} that "
                f"the read-only provider cannot supply from this request; scope the "
                f"server via {hint} (or map the capability with "
                f"MCP_{server.upper()}_MAP)"
            )
        for key in properties:
            if key in arguments:
                continue
            value = match(key)
            if value is not None and value != "":
                arguments[key] = value
        return arguments

    @staticmethod
    def _not_found(exc: MCPProviderError) -> bool:
        text = str(exc).lower()
        return any(marker in text for marker in NOT_FOUND_MARKERS)

    # ---------------------------------------------------------------- GitHub

    def search_github(
        self,
        query: str = "",
        project_id: str = "",
        kind: str = "issues",
        limit: int = 10,
    ) -> List[MCPRecord]:
        if kind not in GITHUB_SEARCH_KINDS:
            raise MCPProviderError(f"unsupported GitHub search kind: {kind!r}")
        tool = self._resolve(self._github_conn, f"search.{kind}")
        values = self._scoping_values("github")
        values["query"] = query or None
        values["limit"] = limit if limit and limit > 0 else None
        arguments = self._build_arguments(tool, values, "github")
        payload = self._github_conn.call(tool.name, arguments)
        records = [self._github_record(kind, item) for item in _as_list(payload, f"github {kind}")]
        if limit and limit > 0:
            records = records[:limit]
        return records

    def get_github_repository(self, repository_id: str) -> Optional[MCPRecord]:
        return self._get_github("get.repository", repository_id, "repository")

    def get_github_issue(self, number: int) -> Optional[MCPRecord]:
        return self._get_github("get.issue", number, "issue")

    def get_github_pull_request(self, number: int) -> Optional[MCPRecord]:
        return self._get_github("get.pull_request", number, "pull_request")

    def get_github_commit(self, sha: str) -> Optional[MCPRecord]:
        return self._get_github("get.commit", sha, "commit")

    def get_github_review(self, review_id: str) -> Optional[MCPRecord]:
        return self._get_github("get.review", review_id, "review")

    def _get_github(self, op_key: str, identity: Any, kind: str) -> Optional[MCPRecord]:
        tool = self._resolve(self._github_conn, op_key)
        values = self._scoping_values("github")
        if kind == "repository":
            repository = str(identity)
            values["repository_id"] = repository
            values["repository"] = repository
            if "/" in repository:
                owner, repo = _split_owner_repo(repository)
                values.setdefault("owner", owner)
                values.setdefault("repo", repo)
        elif kind in ("issue", "pull_request"):
            values["number"] = _as_int(identity, f"{kind} number")
        else:
            values["sha" if kind == "commit" else "review_id"] = str(identity)
            if kind == "review":
                values["id"] = str(identity)
        arguments = self._build_arguments(tool, values, "github")
        try:
            payload = self._github_conn.call(tool.name, arguments)
        except MCPProviderError as exc:
            if self._not_found(exc):
                return None
            raise
        obj = _as_object(payload, f"github {kind}")
        if obj is None:
            return None
        return self._github_record(kind, obj)

    def _github_record(self, kind: str, obj: Dict[str, Any]) -> MCPRecord:
        if kind in ("issue", "issues"):
            return self._issue_record(obj)
        if kind in ("pull_request", "pull_requests", "pr"):
            return self._pr_record(obj)
        if kind in ("commit", "commits"):
            return self._commit_record(obj)
        if kind in ("review", "reviews"):
            return self._review_record(obj)
        return self._repository_record(obj)

    def _scope_repository(self, obj: Dict[str, Any]) -> str:
        direct = _first(
            obj.get("repository"),
            obj.get("repo"),
            obj.get("repository_full_name"),
            obj.get("full_name"),
        )
        if isinstance(direct, dict):
            name = direct.get("full_name") or direct.get("name") or ""
            if name:
                return str(name)
        elif isinstance(direct, str) and direct:
            return direct
        for key in ("repository_url", "html_url", "url"):
            url = obj.get(key)
            if isinstance(url, str) and url.startswith("http"):
                derived = _repository_from_url(url)
                if derived:
                    return derived
        owner = os.getenv("MCP_GITHUB_OWNER", "").strip()
        repo = os.getenv("MCP_GITHUB_REPO", "").strip()
        if owner and repo:
            return f"{owner}/{repo}"
        return ""

    def _issue_record(self, obj: Dict[str, Any]) -> MCPRecord:
        number = obj.get("number")
        if number is None:
            raise MCPProviderError("malformed GitHub issue payload: missing 'number'")
        number = _as_int(number, "issue number")
        data: Dict[str, Any] = {"number": number}
        _put(data, "id", obj.get("id"))
        _put(data, "title", obj.get("title"))
        _put(data, "body", _first(obj.get("body"), obj.get("body_text")))
        _put(data, "status", _first(obj.get("status"), obj.get("state")))
        _put(data, "author", _first(_login(obj.get("author")), _login(obj.get("user")), _login(obj.get("created_by"))))
        labels = _labels(obj.get("labels"))
        if labels:
            data["labels"] = labels
        _put(data, "url", _first(obj.get("html_url"), obj.get("url")))
        _put(data, "created_at", obj.get("created_at"))
        _put(data, "updated_at", obj.get("updated_at"))
        _put(data, "repository", self._scope_repository(obj))
        return MCPRecord(
            source="GitHub",
            record_type="issue",
            source_id=f"Issue #{number}",
            project_id="",
            data=data,
            source_mode="real",
        )

    def _pr_record(self, obj: Dict[str, Any]) -> MCPRecord:
        number = obj.get("number")
        if number is None:
            raise MCPProviderError("malformed GitHub pull request payload: missing 'number'")
        number = _as_int(number, "pull request number")
        data: Dict[str, Any] = {"number": number}
        _put(data, "id", obj.get("id"))
        _put(data, "title", obj.get("title"))
        _put(data, "summary", _first(obj.get("summary"), obj.get("body"), obj.get("body_text")))
        _put(data, "status", _first(obj.get("status"), obj.get("state")))
        _put(data, "author", _first(_login(obj.get("author")), _login(obj.get("user"))))
        reviewers = [
            _login(entry)
            for entry in (obj.get("requested_reviewers") or obj.get("reviewers") or [])
        ]
        reviewers = [name for name in reviewers if name]
        if reviewers:
            data["reviewers"] = reviewers
        _put(data, "url", _first(obj.get("html_url"), obj.get("url")))
        _put(data, "created_at", obj.get("created_at"))
        _put(data, "updated_at", obj.get("updated_at"))
        _put(data, "repository", self._scope_repository(obj))
        return MCPRecord(
            source="GitHub",
            record_type="pull_request",
            source_id=f"PR #{number}",
            project_id="",
            data=data,
            source_mode="real",
        )

    def _commit_record(self, obj: Dict[str, Any]) -> MCPRecord:
        sha = _first(obj.get("sha"), obj.get("commit_sha"))
        if not sha:
            raise MCPProviderError("malformed GitHub commit payload: missing 'sha'")
        inner = obj.get("commit") if isinstance(obj.get("commit"), dict) else {}
        inner_author = inner.get("author") if isinstance(inner.get("author"), dict) else {}
        data: Dict[str, Any] = {"sha": str(sha)}
        _put(data, "message", _first(obj.get("message"), inner.get("message")))
        _put(
            data,
            "author",
            _first(_login(obj.get("author")), obj.get("author_name"), inner_author.get("name")),
        )
        _put(
            data,
            "timestamp",
            _first(obj.get("timestamp"), obj.get("date"), inner_author.get("date")),
        )
        _put(data, "url", _first(obj.get("html_url"), obj.get("url")))
        pr_number = _first(obj.get("pr_number"), obj.get("pull_request_number"))
        if pr_number is not None:
            _put(data, "pr_number", pr_number)
        _put(data, "repository", self._scope_repository(obj))
        return MCPRecord(
            source="GitHub",
            record_type="commit",
            source_id=str(sha),
            project_id="",
            data=data,
            source_mode="real",
        )

    def _review_record(self, obj: Dict[str, Any]) -> MCPRecord:
        review_id = _first(obj.get("id"), obj.get("review_id"))
        if review_id is None or review_id == "":
            raise MCPProviderError("malformed GitHub review payload: missing 'id'")
        review_id = str(review_id)
        data: Dict[str, Any] = {"id": review_id}
        pr_number = _first(obj.get("pull_request_number"), obj.get("pr_number"))
        pull = obj.get("pull_request")
        if pr_number is None and isinstance(pull, dict):
            pr_number = _first(pull.get("number"))
            if pr_number is None and isinstance(pull.get("url"), str):
                segments = pull["url"].rstrip("/").split("/")
                if segments and segments[-1].isdigit():
                    pr_number = int(segments[-1])
        if pr_number is None and isinstance(pull, str) and "/" in pull:
            segments = pull.rstrip("/").split("/")
            if segments and segments[-1].isdigit():
                pr_number = int(segments[-1])
        if pr_number is not None:
            data["pr_number"] = _as_int(pr_number, "pull request number")
        _put(data, "state", _first(obj.get("state"), obj.get("status")))
        _put(data, "body", _first(obj.get("body"), obj.get("body_text")))
        _put(
            data,
            "reviewer",
            _first(_login(obj.get("reviewer")), _login(obj.get("user")), _login(obj.get("author"))),
        )
        _put(data, "submitted_at", _first(obj.get("submitted_at"), obj.get("created_at")))
        _put(data, "url", _first(obj.get("html_url"), obj.get("url")))
        return MCPRecord(
            source="GitHub",
            record_type="review",
            source_id=review_id,
            project_id="",
            data=data,
            source_mode="real",
        )

    def _repository_record(self, obj: Dict[str, Any]) -> MCPRecord:
        repo_id = _first(obj.get("id"), obj.get("full_name"))
        name = _first(obj.get("name"), obj.get("full_name"))
        if repo_id is None or not name:
            raise MCPProviderError(
                "malformed GitHub repository payload: missing 'id'/'name'"
            )
        data: Dict[str, Any] = {"id": str(repo_id), "name": str(name)}
        owner = obj.get("owner")
        org = _login(owner) if owner is not None else ""
        if not org and isinstance(obj.get("full_name"), str) and "/" in obj["full_name"]:
            org = obj["full_name"].split("/", 1)[0]
        _put(data, "org", org)
        _put(data, "url", _first(obj.get("html_url"), obj.get("url")))
        _put(data, "open_issues_count", obj.get("open_issues_count"))
        _put(data, "description", obj.get("description"))
        _put(data, "updated_at", _first(obj.get("updated_at"), obj.get("pushed_at")))
        return MCPRecord(
            source="GitHub",
            record_type="repository",
            source_id=str(repo_id),
            project_id="",
            data=data,
            source_mode="real",
        )

    # ----------------------------------------------------------------- Gmail

    def search_gmail(
        self,
        query: str = "",
        project_id: str = "",
        kind: str = "threads",
        thread_id: str = "",
        limit: int = 10,
    ) -> List[MCPRecord]:
        if kind not in GMAIL_SEARCH_KINDS:
            raise MCPProviderError(f"unsupported Gmail search kind: {kind!r}")
        tool = self._resolve(self._gmail_conn, f"search.{kind}")
        values = self._scoping_values("gmail")
        values["query"] = query or None
        values["thread_id"] = thread_id or None
        values["limit"] = limit if limit and limit > 0 else None
        arguments = self._build_arguments(tool, values, "gmail")
        payload = self._gmail_conn.call(tool.name, arguments)
        records = [self._gmail_record(kind, item) for item in _as_list(payload, f"gmail {kind}")]
        if limit and limit > 0:
            records = records[:limit]
        return records

    def get_gmail_thread(self, thread_id: str) -> Optional[MCPRecord]:
        tool = self._resolve(self._gmail_conn, "get.thread")
        values = self._scoping_values("gmail")
        values["thread_id"] = thread_id
        values["id"] = thread_id
        arguments = self._build_arguments(tool, values, "gmail")
        try:
            payload = self._gmail_conn.call(tool.name, arguments)
        except MCPProviderError as exc:
            if self._not_found(exc):
                return None
            raise
        obj = _as_object(payload, "gmail thread")
        if obj is None:
            return None
        return self._gmail_record("threads", obj)

    def get_gmail_message(self, message_id: str) -> Optional[MCPRecord]:
        tool = self._resolve(self._gmail_conn, "get.message")
        values = self._scoping_values("gmail")
        values["message_id"] = message_id
        values["id"] = message_id
        arguments = self._build_arguments(tool, values, "gmail")
        try:
            payload = self._gmail_conn.call(tool.name, arguments)
        except MCPProviderError as exc:
            if self._not_found(exc):
                return None
            raise
        obj = _as_object(payload, "gmail message")
        if obj is None:
            return None
        return self._gmail_record("messages", obj)

    def _gmail_record(self, kind: str, obj: Dict[str, Any]) -> MCPRecord:
        if kind == "threads":
            return self._thread_record(obj)
        return self._email_record(obj)

    def _thread_record(self, obj: Dict[str, Any]) -> MCPRecord:
        thread_id = _first(obj.get("id"), obj.get("thread_id"), obj.get("threadId"))
        if not thread_id:
            raise MCPProviderError("malformed Gmail thread payload: missing 'id'")
        thread_id = str(thread_id)
        messages = obj.get("messages") if isinstance(obj.get("messages"), list) else []
        headers = _message_headers(messages[0]) if messages else {}
        participants: List[str] = []
        for message in messages:
            message_headers = _message_headers(message)
            for key in ("from", "to"):
                for address in _split_addresses(message_headers.get(key, "")):
                    if address and address not in participants:
                        participants.append(address)
        flat_participants = obj.get("participants")
        if isinstance(flat_participants, list):
            for address in flat_participants:
                if address and str(address) not in participants:
                    participants.append(str(address))
        data: Dict[str, Any] = {"id": thread_id}
        _put(data, "subject", _first(obj.get("subject"), headers.get("subject")))
        _put(data, "snippet", _first(obj.get("snippet"), obj.get("preview")))
        if participants:
            data["participants"] = participants
        if messages:
            data["message_count"] = len(messages)
        _put(data, "last_message_at", _iso(_first(obj.get("last_message_at"), obj.get("internalDate"))))
        _put(data, "created_at", _iso(obj.get("created_at")))
        _put(data, "url", obj.get("url"))
        return MCPRecord(
            source="Gmail",
            record_type="thread",
            source_id=thread_id,
            project_id="",
            data=data,
            source_mode="real",
        )

    def _email_record(self, obj: Dict[str, Any]) -> MCPRecord:
        message_id = _first(obj.get("id"), obj.get("message_id"), obj.get("messageId"))
        if not message_id:
            raise MCPProviderError("malformed Gmail message payload: missing 'id'")
        message_id = str(message_id)
        headers = _message_headers(obj)
        sender = str(_first(obj.get("sender"), obj.get("from"), headers.get("from")) or "")
        recipients = obj.get("recipients")
        if not isinstance(recipients, list):
            to_value = _first(headers.get("to"), obj.get("to"))
            if isinstance(to_value, list):
                recipients = to_value
            else:
                recipients = _split_addresses(str(to_value or ""))
        recipients = [str(item) for item in recipients if item]
        body = _first(
            obj.get("body"),
            obj.get("bodyPlain"),
            obj.get("body_text"),
            obj.get("text"),
            obj.get("snippet"),
        )
        data: Dict[str, Any] = {"id": message_id, "subject": str(headers.get("subject") or obj.get("subject") or "")}
        thread_id = _first(obj.get("thread_id"), obj.get("threadId"))
        if thread_id:
            data["thread_id"] = str(thread_id)
        _put(data, "sender", sender)
        _put(data, "sender_email", _sender_email(sender))
        if recipients:
            data["recipients"] = recipients
        _put(data, "body", body)
        received = _first(
            obj.get("received_at"),
            _iso(obj.get("internalDate")) or None,
            obj.get("date"),
        )
        _put(data, "received_at", received)
        return MCPRecord(
            source="Gmail",
            record_type="email",
            source_id=message_id,
            project_id="",
            data=data,
            relationships={"thread": str(thread_id or "")},
            source_mode="real",
        )

    # ---------------------------------------------------------- Relationships

    def get_cross_source_links(self, project_id: str = "") -> List[MCPRecord]:
        return []

    # ----------------------------------------------------------------- Health

    def health_check(self) -> MCPHealthReport:
        return build_health_report(self.provider_name, self.github_health(), self.gmail_health())

    def github_health(self) -> MCPHealth:
        return self._connection_health(self._github_conn)

    def gmail_health(self) -> MCPHealth:
        return self._connection_health(self._gmail_conn)

    @staticmethod
    def _connection_health(conn: MCPConnection) -> MCPHealth:
        outcome = conn.discover()
        connected = outcome.state == STATE_CONNECTED
        return MCPHealth(
            server=conn.server,
            provider="real",
            healthy=connected,
            mock_connected=False,
            message=outcome.message,
            endpoint=conn.endpoint_display(),
            records_available=None,
            status=outcome.state,
            tools=outcome.tool_names if connected else [],
        )
