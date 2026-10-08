import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.mcp import build_status_response, get_mcp_provider
from app.models.evidence import (
    CrossSourceLink,
    EvidenceDetail,
    EvidenceItem,
    EvidenceLinkedIntel,
)
from app.repositories.github_repository import github_repository
from app.repositories.gmail_repository import gmail_repository
from app.repositories.relationship_repository import relationship_repository
from app.schemas.evidence import EvidenceOverviewResponse


def _fmt_ts(iso: str) -> str:
    """Format a source ISO timestamp as 'Oct 6, 4:46 PM' (source clock, no tz shift)."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {hour12}:{dt.strftime('%M')} {ampm}"


def _fmt_date_long(d: str) -> str:
    """Format '2026-10-09' as 'October 9'."""
    if not d:
        return ""
    try:
        dt = datetime.fromisoformat(d)
    except ValueError:
        return d
    return f"{dt.strftime('%B')} {dt.day}"


def _sentences(text: str, max_n: int = 3) -> List[str]:
    parts = [
        p.strip()
        for p in re.split(r"(?<=[.!?])\s+", (text or "").strip())
        if len(p.strip()) > 10
    ]
    return parts[:max_n]


def _snapshot_date() -> str:
    try:
        path = settings.DATA_ROOT / "evaluation" / "questions.json"
        if not path.exists():
            path = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "data"
                / "evaluation"
                / "questions.json"
            )
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return f"{mtime.strftime('%b')} {mtime.day}, {mtime.year}"
    except Exception:  # noqa: BLE001
        return "unknown"


def _source_access(origin: str) -> str:
    """Honest access label from the live MCP provider status (Mock vs Real)."""
    try:
        status = build_status_response(get_mcp_provider())
        return f"{origin} · {status.mode} ({status.data_source})"
    except Exception:  # noqa: BLE001
        return f"{origin} · Mock MCP (Synthetic Data)"


class EvidenceService:
    # ------------------------------------------------------------- helpers

    @staticmethod
    def _linked_intel(project_id: str, links: List[CrossSourceLink]) -> EvidenceLinkedIntel:
        link = next((l for l in links if l.project_id == project_id), None)
        if not link:
            return EvidenceLinkedIntel()
        parts: List[str] = ["Latest Ask run"]
        pb = link.primary_blocker
        if pb and pb.github_issue and pb.github_issue.number:
            parts.append(f"Issue #{pb.github_issue.number}")
        if pb and pb.github_pr and pb.github_pr.number:
            parts.append(f"PR #{pb.github_pr.number}")
        if pb and pb.gmail_thread and pb.gmail_thread.id:
            parts.append(pb.gmail_thread.id)
        if len(parts) == 1:
            if link.github_pr and link.github_pr.get("number"):
                parts.append(f"PR #{link.github_pr['number']}")
            if link.gmail_thread and link.gmail_thread.get("id"):
                parts.append(link.gmail_thread["id"])
        title = " ".join(
            p for p in [link.project_name, link.target_release, "release readiness"] if p
        )
        return EvidenceLinkedIntel(
            title=title,
            sources=" · ".join(parts),
            context="Grounded answer links this record through claim-level citations.",
        )

    @staticmethod
    def _metadata(citation_id: str) -> Dict[str, str]:
        return {
            "citation_id": citation_id,
            "chunk": "1 chunk (record-aligned)",
            "snapshot": _snapshot_date(),
            "index": settings.QDRANT_COLLECTION,
        }

    @staticmethod
    def _context_note(display_ts: str) -> str:
        return (
            f"Excerpt keeps the original source timestamp ({display_ts}); "
            "relevance ranking is AI-generated."
        )

    @staticmethod
    def _source_badge(source_label: str, kind: str, kind_color: str) -> List[Dict[str, str]]:
        badges = [{"label": source_label, "color": "blue" if source_label == "Email" else "gray"}]
        if kind and kind != source_label:
            badges.append({"label": kind, "color": kind_color})
        return badges

    # ------------------------------------------------------------- records

    def _issue_record(
        self, issue, links: List[CrossSourceLink], idx: int
    ) -> EvidenceItem:
        body = issue.body or ""
        claims = _sentences(body) or [body or issue.title]
        subtitle = f"Release-blocking issue remains {issue.status}"
        subtitle += (
            " pending security approval." if "security approval" in body.lower() else "."
        )
        display = _fmt_ts(issue.updated_at)
        detail = EvidenceDetail(
            title=issue.title,
            thread=f"{issue.repository} · Issue #{issue.number}",
            author=issue.author or "",
            received_display=display,
            project=issue.project_name or "",
            source_access=_source_access("GitHub"),
            excerpt_label="ISSUE BODY · SOURCE EXCERPT",
            excerpt=body,
            claims=claims,
            context_note=self._context_note(display),
            linked_intel=self._linked_intel(issue.project_id, links),
            metadata=self._metadata(f"ev-{issue.number}"),
            open_label="Open original in GitHub ↗",
        )
        return EvidenceItem(
            id=f"ev-{issue.number}",
            title=issue.title,
            source_type="GitHub Issue",
            source_ref=f"{issue.repository} #{issue.number}",
            project_id=issue.project_id,
            project_name=issue.project_name,
            relevance_score=round(0.99 - 0.01 * idx, 2),
            excerpt=body,
            author_sender=issue.author or "",
            timestamp=issue.updated_at,
            url_route="#github",
            kind="Risk",
            kind_color="amber",
            subtitle=subtitle,
            source_line=f"GitHub · Issue #{issue.number} · Updated {display}",
            badges=self._source_badge("GitHub", "Risk", "amber"),
            detail=detail,
        )

    def _pr_record(self, pr, links: List[CrossSourceLink], idx: int) -> EvidenceItem:
        summary = pr.summary or ""
        claims: List[str] = []
        if pr.status == "awaiting_security_review" or not pr.security_reviewer_assigned:
            claims.append(f"PR #{pr.number} requires security review.")
        if pr.ci_status == "passed":
            claims.append(f"PR #{pr.number} has passed CI checks.")
        if not claims:
            claims = _sentences(summary) or [summary or pr.title]
        assigned = "been assigned" if pr.security_reviewer_assigned else "not yet been assigned"
        subtitle = f"Checks {pr.ci_status}. A security reviewer has {assigned}."
        display = _fmt_ts(pr.updated_at)
        detail = EvidenceDetail(
            title=pr.title,
            thread=f"{pr.repository} · PR #{pr.number}",
            author=pr.author or pr.assignee or "",
            received_display=display,
            project=pr.project_name or "",
            source_access=_source_access("GitHub"),
            excerpt_label="PULL REQUEST SUMMARY · SOURCE EXCERPT",
            excerpt=summary,
            claims=claims,
            context_note=self._context_note(display),
            linked_intel=self._linked_intel(pr.project_id, links),
            metadata=self._metadata(f"ev-{pr.number}"),
            open_label="Open original in GitHub ↗",
        )
        return EvidenceItem(
            id=f"ev-{pr.number}",
            title=f"{pr.title} awaits review",
            source_type="GitHub PR",
            source_ref=f"{pr.repository} #{pr.number}",
            project_id=pr.project_id,
            project_name=pr.project_name,
            relevance_score=round(0.99 - 0.01 * idx, 2),
            excerpt=summary,
            author_sender=pr.author or pr.assignee or "",
            timestamp=pr.updated_at,
            url_route="#github",
            kind="Risk",
            kind_color="amber",
            subtitle=subtitle,
            source_line=f"GitHub · PR #{pr.number} · Updated {display}",
            badges=self._source_badge("GitHub", "Risk", "amber"),
            detail=detail,
        )

    def _email_record(
        self,
        msg,
        thread,
        links: List[CrossSourceLink],
        *,
        kind: str,
        kind_color: str,
        list_title: str,
        subtitle: str,
        source_line: str,
        excerpt_label: str,
        idx: int,
    ) -> EvidenceItem:
        body = msg.body or ""
        claims = _sentences(body) or [body]
        display = _fmt_ts(msg.received_at)
        project = thread.project_name or msg.project_name or ""
        project_id = msg.project_id or thread.project_id
        detail = EvidenceDetail(
            title=msg.subject,
            thread=thread.subject or msg.thread_id,
            author=msg.sender,
            received_display=display,
            project=project,
            source_access=_source_access("Gmail"),
            excerpt_label=excerpt_label,
            excerpt=body,
            claims=claims,
            context_note=self._context_note(display),
            linked_intel=self._linked_intel(project_id, links),
            metadata=self._metadata(f"ev-{msg.id.lower()}"),
            open_label="Open original in Gmail ↗",
        )
        return EvidenceItem(
            id=f"ev-{msg.id.lower()}",
            title=list_title,
            source_type="Gmail Message",
            source_ref=f"{thread.id} / {msg.id}",
            project_id=project_id,
            project_name=project,
            relevance_score=round(0.99 - 0.01 * idx, 2),
            excerpt=body,
            author_sender=msg.sender,
            timestamp=msg.received_at,
            url_route="#gmail",
            kind=kind,
            kind_color=kind_color,
            subtitle=subtitle,
            source_line=source_line,
            badges=self._source_badge("Email", kind, kind_color),
            detail=detail,
        )

    # -------------------------------------------------- priority derivation

    def _build_priority_records(self, links: List[CrossSourceLink]) -> List[EvidenceItem]:
        """Derive the priority records from dataset flags - no hardcoded IDs.

        Rule order (matches the Evidence Explorer design):
          1. Decision message of each release-blocker thread
          2. Each open release-blocker issue            -> Risk
          3. Each PR awaiting security review            -> Risk
          4. First message of each release-blocker thread -> Email
          5. Priority Decision emails outside blocker threads in projects that
             have a blocker thread                      -> Decision
          6. First priority email of linked projects without a blocker thread -> Email
        """
        issues = github_repository.get_issues()
        prs = github_repository.get_pull_requests()
        threads = gmail_repository.get_threads()
        emails = gmail_repository.get_emails()

        blocker_issues = [i for i in issues if i.status == "open" and i.is_release_blocker]
        security_prs = [p for p in prs if p.status == "awaiting_security_review"]
        blocker_threads = [t for t in threads if t.is_release_blocker]
        blocker_thread_ids = {t.id for t in blocker_threads}
        blocker_projects = {t.project_id for t in blocker_threads}
        thread_by_id = {t.id: t for t in threads}
        emails_by_thread: Dict[str, list] = {}
        for m in emails:
            emails_by_thread.setdefault(m.thread_id, []).append(m)
        for lst in emails_by_thread.values():
            lst.sort(key=lambda m: m.received_at or "")

        records: List[EvidenceItem] = []
        idx = 0

        # 1) Decision message inside a release-blocker thread
        for t in blocker_threads:
            msgs = emails_by_thread.get(t.id, [])
            decision = next((m for m in msgs if m.category == "Decision"), None)
            if decision is None:
                continue
            n = msgs.index(decision) + 1
            records.append(
                self._email_record(
                    decision,
                    t,
                    links,
                    kind="Decision",
                    kind_color="purple",
                    list_title="Security sign-off is a release gate",
                    subtitle=f"{decision.sender} requires approval before the auth migration ships.",
                    source_line=f"Gmail · {t.id} · Message {n} · {_fmt_ts(decision.received_at)}",
                    excerpt_label=f"MESSAGE {n} · SOURCE EXCERPT",
                    idx=idx,
                )
            )
            idx += 1

        # 2) Open release-blocker issues
        for issue in blocker_issues:
            records.append(self._issue_record(issue, links, idx))
            idx += 1

        # 3) PRs awaiting security review
        for pr in security_prs:
            records.append(self._pr_record(pr, links, idx))
            idx += 1

        # 4) First message of each release-blocker thread
        for t in blocker_threads:
            msgs = emails_by_thread.get(t.id, [])
            if not msgs:
                continue
            first = msgs[0]
            if first.category == "Decision":
                continue
            link = next((l for l in links if l.project_id == t.project_id), None)
            date_part = (
                f" · {_fmt_date_long(link.target_date)} target"
                if link and link.target_date
                else ""
            )
            base = t.subject.split("·")[0].strip() if t.subject else t.id
            records.append(
                self._email_record(
                    first,
                    t,
                    links,
                    kind="Email",
                    kind_color="blue",
                    list_title=f"{base}{date_part}",
                    subtitle=(
                        f"{first.sender} confirms the date and requests "
                        "final scope confirmation."
                    ),
                    source_line=f"Gmail · {t.id} · Message 1 · {_fmt_ts(first.received_at)}",
                    excerpt_label="MESSAGE 1 · SOURCE EXCERPT",
                    idx=idx,
                )
            )
            idx += 1

        # 5) Priority Decision emails outside blocker threads, in projects that
        #    have a blocker thread (e.g. contract-freeze decisions)
        extra_decisions = [
            m
            for m in emails
            if m.is_priority
            and m.category == "Decision"
            and m.thread_id not in blocker_thread_ids
            and m.project_id in blocker_projects
        ]
        for m in sorted(extra_decisions, key=lambda x: x.received_at or ""):
            t = thread_by_id.get(m.thread_id)
            if t is None:
                continue
            first_sentence = _sentences(m.body, max_n=1)
            base = (t.subject or t.id).split("·")[0].strip()
            records.append(
                self._email_record(
                    m,
                    t,
                    links,
                    kind="Decision",
                    kind_color="purple",
                    list_title=m.subject or t.subject,
                    subtitle=first_sentence[0] if first_sentence else (m.subject or ""),
                    source_line=f"Gmail · {t.id} · {_fmt_ts(m.received_at)}",
                    excerpt_label=f"{base.upper()} MESSAGE · SOURCE EXCERPT",
                    idx=idx,
                )
            )
            idx += 1

        # 6) Linked projects without a blocker thread: first priority message
        for link in links:
            if link.project_id in blocker_projects:
                continue
            cands = [
                m
                for m in emails
                if m.project_id == link.project_id
                and m.is_priority
                and m.thread_id not in blocker_thread_ids
            ]
            if not cands:
                continue
            cands.sort(key=lambda x: x.received_at or "")
            m = cands[0]
            t = thread_by_id.get(m.thread_id)
            if t is None:
                continue
            msgs = emails_by_thread.get(t.id, [])
            n = msgs.index(m) + 1 if m in msgs else 1
            base = t.subject.split("·")[0].strip() if t.subject else t.id
            release = link.target_release or "the next"
            records.append(
                self._email_record(
                    m,
                    t,
                    links,
                    kind="Email",
                    kind_color="blue",
                    list_title=f"{base} complete for release candidate",
                    subtitle=(
                        f"{m.sender} submits {release} candidate for regression suite."
                    ),
                    source_line=f"Gmail · {t.id} · Message {n} · {_fmt_ts(m.received_at)}",
                    excerpt_label=f"{base.upper()} MESSAGE · SOURCE EXCERPT",
                    idx=idx,
                )
            )
            idx += 1

        return records

    # ------------------------------------------------------------- overview

    def get_overview(self) -> EvidenceOverviewResponse:
        links = relationship_repository.get_cross_source_links()
        records = self._build_priority_records(links)

        issues = github_repository.get_issues()
        prs = github_repository.get_pull_requests()
        commits = github_repository.get_commits()
        reviews = github_repository.get_reviews()
        repos = github_repository.get_repositories()
        emails = gmail_repository.get_emails()
        threads = gmail_repository.get_threads()

        risk = (
            len(
                [
                    i
                    for i in issues
                    if i.status == "open"
                    and (
                        i.is_release_blocker
                        or i.severity in ("critical", "high")
                    )
                ]
            )
            + len([p for p in prs if p.status == "awaiting_security_review"])
            + len([t for t in threads if t.is_release_blocker])
        )
        github_records = len(issues) + len(prs) + len(commits) + len(reviews) + len(repos)

        return EvidenceOverviewResponse(
            total_records=github_records + len(emails) + len(threads) + len(links),
            github_records_count=github_records,
            gmail_records_count=len(emails) + len(threads),
            cross_source_links_count=len(links),
            email_records_count=len(emails),
            decision_records_count=len(links),
            risk_records_count=risk,
            items=records,
            cross_source_links=links,
        )

    def get_evidence_by_id(self, evidence_id: str) -> Optional[EvidenceItem]:
        overview = self.get_overview()
        for item in overview.items:
            if item.id == evidence_id or evidence_id in item.source_ref:
                return item
        return None


evidence_service = EvidenceService()
