import re
import time
from collections import OrderedDict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.llm import build_llm_status
from app.mcp import build_status_response, get_mcp_provider
from app.rag import rag_service
from app.agents.orchestrator import run_store
from app.repositories.github_repository import github_repository
from app.repositories.gmail_repository import gmail_repository
from app.repositories.project_repository import project_repository
from app.repositories.relationship_repository import relationship_repository
from app.schemas.report import (
    ReportAction,
    ReportBlocker,
    ReportCitation,
    ReportDocument,
    ReportFinding,
    ReportGenerateResponse,
    ReportProvenance,
    ReportRecent,
    ReportRisk,
)

INACTIVE_PR_STATUSES = ("merged", "closed")


def _fmt_ts(iso: str) -> str:
    """'2026-10-06T16:46:00Z' -> 'Oct 6, 4:46 PM'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {hour12}:{dt.strftime('%M')} {ampm}"


def _fmt_cite(iso: str) -> str:
    """'2026-10-06T16:46:00Z' -> 'Oct 6 · 4:46 PM'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day} · {hour12}:{dt.strftime('%M')} {ampm}"


def _fmt_date_long(d: str) -> str:
    """'2026-10-09' -> 'October 9'."""
    if not d:
        return ""
    try:
        dt = datetime.fromisoformat(d)
    except ValueError:
        return d
    return f"{dt.strftime('%B')} {dt.day}"


def _fmt_date_short(d: str) -> str:
    """'2026-10-09' -> 'Oct 8'."""
    if not d:
        return ""
    try:
        dt = datetime.fromisoformat(d)
    except ValueError:
        return d
    return f"{dt.strftime('%b')} {dt.day}"


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


class ReportService:
    """Builds the release-readiness report from repository data only.

    Provenance values (agent run, MCP/RAG/LLM mode, generation time) come from
    the live service status - never from invented demo metrics.
    """

    def __init__(self) -> None:
        self._store: "OrderedDict[str, OrderedDict[str, ReportDocument]]" = OrderedDict()
        self._max_reports_per_project = 5

    # ------------------------------------------------------------- storage

    def _remember(self, report: ReportDocument) -> None:
        project_reports = self._store.setdefault(report.project_id, OrderedDict())
        project_reports[report.report_id] = report
        project_reports.move_to_end(report.report_id)
        while len(project_reports) > self._max_reports_per_project:
            project_reports.popitem(last=False)

    def _recent(self, project_id: str) -> List[ReportRecent]:
        project_reports = self._store.get(project_id, {})
        entries = list(project_reports.values())[::-1]
        return [
            ReportRecent(
                report_id=r.report_id,
                project_id=r.project_id,
                title=r.title,
                generated_at=r.generated_at,
                status=r.status,
            )
            for r in entries
        ]

    def latest(self, project_id: str) -> ReportGenerateResponse:
        project_reports = self._store.get(project_id, {})
        report = next(iter(reversed(project_reports.values())), None)
        return ReportGenerateResponse(report=report, recent=self._recent(project_id))

    # --------------------------------------------------------- derivations

    @staticmethod
    def _project_scope(project):
        repo_names = list(project.repositories or [])
        issues = [
            i
            for i in github_repository.get_issues()
            if i.status == "open"
            and (i.project_id == project.id or i.repository in repo_names)
        ]
        prs = [
            p
            for p in github_repository.get_pull_requests()
            if p.status not in INACTIVE_PR_STATUSES
            and (p.project_id == project.id or p.repository in repo_names)
        ]
        emails = [e for e in gmail_repository.get_emails() if e.project_id == project.id]
        threads = [t for t in gmail_repository.get_threads() if t.project_id == project.id]
        return repo_names, issues, prs, emails, threads

    @staticmethod
    def _reporting_period(issues, prs, emails) -> str:
        dates: List[str] = []
        for e in emails:
            if e.received_at:
                dates.append(e.received_at[:10])
        for recs in (issues, prs):
            for r in recs:
                stamp = r.created_at or r.updated_at
                if stamp:
                    dates.append(stamp[:10])
        if not dates:
            return "N/A — not measured"
        d1, d2 = min(dates), max(dates)
        try:
            dt1, dt2 = date.fromisoformat(d1), date.fromisoformat(d2)
        except ValueError:
            return "N/A — not measured"
        if dt1.year == dt2.year and dt1.month == dt2.month:
            return f"{dt1.strftime('%B')} {dt1.day}-{dt2.day}, {dt1.year}"
        return (
            f"{dt1.strftime('%B')} {dt1.day} - "
            f"{dt2.strftime('%B')} {dt2.day}, {dt2.year}"
        )

    # -------------------------------------------------------- provenance

    @staticmethod
    def _provenance(run_id: str, elapsed_ms: int) -> ReportProvenance:
        try:
            mcp = build_status_response(get_mcp_provider())
            mcp_text = f"{mcp.mode} · {mcp.data_source}"
        except Exception:  # noqa: BLE001
            mcp_text = "Mock MCP · Synthetic Data"
        try:
            rag = rag_service.get_status()
            rag_text = (
                f"{rag.status} · {rag.collection} · {rag.documents} docs / "
                f"{rag.chunks} chunks"
            )
        except Exception:  # noqa: BLE001
            rag_text = "unavailable"
        try:
            llm = build_llm_status()
            llm_text = f"{llm.status} · {llm.provider} · {llm.model}"
        except Exception:  # noqa: BLE001
            llm_text = "unavailable"
        agent_run = run_id if run_id else "N/A — not measured"
        generation = f"{elapsed_ms} ms (measured)"
        note = (
            "Counts are calculated from the current GitHub + Gmail dataset "
            "snapshot (calculated values). The project health score is a dataset "
            "project field (dataset value), not a release approval. "
            f"Agent run: {agent_run}. Generation time: {generation}. "
            f"MCP: {mcp_text}. RAG: {rag_text}. LLM: {llm_text}."
        )
        return ReportProvenance(
            status="Complete",
            sources="GitHub + Gmail",
            agent_run=agent_run,
            generation=generation,
            mcp=mcp_text,
            rag=rag_text,
            llm=llm_text,
            note=note,
        )

    # ------------------------------------------------------------- generate

    def generate(self, project_id: str = "proj-platform-api") -> ReportGenerateResponse:
        t0 = time.perf_counter()
        project = project_repository.get_project_by_id(project_id)
        if project is None:
            projects = project_repository.get_projects()
            project = projects[0] if projects else None
        if project is None:
            raise ValueError("No projects available for report generation")

        now = datetime.now(timezone.utc)
        repo_names, issues, prs, emails, threads = self._project_scope(project)
        links = relationship_repository.get_cross_source_links()
        link = next((l for l in links if l.project_id == project.id), None)

        blocker_issues = [i for i in issues if i.is_release_blocker]
        security_prs = [p for p in prs if p.status == "awaiting_security_review"]
        blocker_threads = [t for t in threads if t.is_release_blocker]
        blocker_thread = blocker_threads[0] if blocker_threads else None

        thread_messages: List = []
        decision_msg = None
        if blocker_thread is not None:
            thread_messages = sorted(
                gmail_repository.get_emails_by_thread_id(blocker_thread.id),
                key=lambda m: m.received_at or "",
            )
            decision_msg = next(
                (m for m in thread_messages if m.category == "Decision"), None
            )

        priority_emails = [e for e in emails if e.is_priority]
        extra_decisions = [
            e
            for e in priority_emails
            if e.category == "Decision"
            and (blocker_thread is None or e.thread_id != blocker_thread.id)
        ]
        extra_decisions.sort(key=lambda e: e.received_at or "")

        # ------------------------------------------------------ citations
        citations: List[ReportCitation] = []
        ref: Dict[str, int] = {}

        def add_citation(kind: str, record: str, ts: str) -> int:
            citations.append(
                ReportCitation(
                    index=len(citations) + 1,
                    kind=kind,
                    record=record,
                    timestamp=_fmt_cite(ts),
                )
            )
            return len(citations)

        for i in blocker_issues:
            ref[f"issue-{i.number}"] = add_citation(
                "Risk", f"GitHub · {i.repository} · Issue #{i.number}", i.updated_at
            )
        for p in security_prs:
            ref[f"pr-{p.number}"] = add_citation(
                "Risk", f"GitHub · {p.repository} · PR #{p.number}", p.updated_at
            )
        for n, m in enumerate(thread_messages, start=1):
            kind = "Decision" if m.category == "Decision" else "Email"
            idx = add_citation(
                kind,
                f"Gmail · {blocker_thread.id} · {m.sender} · Message {n}",
                m.received_at,
            )
            ref[f"msg-{m.id}"] = idx
        latest_pr = None
        if prs:
            latest_pr = max(prs, key=lambda p: p.updated_at or "")
        if latest_pr is not None:
            ref["repos"] = add_citation(
                "Repository snapshot",
                f"GitHub · {len(repo_names)} project repos · PR #{latest_pr.number}",
                latest_pr.updated_at,
            )
        thread_by_id = {t.id: t for t in gmail_repository.get_threads()}
        for m in extra_decisions:
            t = thread_by_id.get(m.thread_id)
            subject = t.subject if t else m.subject
            ref[f"extra-{m.id}"] = add_citation(
                "Decision", f"Gmail · {m.thread_id} · {subject}", m.received_at
            )

        def refs_for(*keys: str) -> List[int]:
            return [ref[k] for k in keys if k in ref]

        def all_indexes() -> List[int]:
            return [c.index for c in citations]

        def ranges(idxs: List[int]) -> str:
            if not idxs:
                return ""
            return "[" + ", ".join(str(i) for i in idxs) + "]"

        # ------------------------------------------------- executive summary
        summary_parts: List[str] = []
        if blocker_issues:
            nums = ", ".join(f"#{i.number}" for i in blocker_issues)
            summary_parts.append(
                f"release-blocking issue{'s' if len(blocker_issues) > 1 else ''} "
                f"{nums} remain{'s' if len(blocker_issues) == 1 else ''} open"
            )
        if security_prs:
            for p in security_prs:
                checks = "has passed checks" if p.ci_status == "passed" else f"CI is {p.ci_status}"
                reviewer = (
                    "has an assigned reviewer"
                    if p.security_reviewer_assigned
                    else "has no assigned security reviewer"
                )
                summary_parts.append(
                    f"PR #{p.number} {checks} but {reviewer}"
                )
        if decision_msg is not None:
            summary_parts.append(
                f"{blocker_thread.id} makes security sign-off a mandatory release gate"
            )
        if not summary_parts:
            summary_parts.append("no release blockers are currently detected")
        status_phrase = (project.status or "On track").lower()
        scope_sentence = ""
        if security_prs and any(
            not p.security_reviewer_assigned for p in security_prs
        ):
            scope_sentence = (
                " Assign a reviewer and confirm the final scope; the evidence "
                "does not yet prove a release delay."
            )
        executive_summary = (
            f"{project.name} is {status_phrase} ahead of its "
            f"{_fmt_date_long(project.target_date)} {project.target_release} target. "
            f"Current findings: " + "; ".join(summary_parts) + f".{scope_sentence} "
            f"{ranges(all_indexes())}"
        ).replace(" ..", ".")

        # ----------------------------------------------------------- risks
        risks: List[ReportRisk] = []
        for i in blocker_issues:
            linked_refs = refs_for(f"issue-{i.number}")
            evidence_bits = [f"Issue #{i.number}"]
            if i.linked_pr_number:
                evidence_bits.append(f"PR #{i.linked_pr_number}")
                linked_refs += refs_for(f"pr-{i.linked_pr_number}")
            risks.append(
                ReportRisk(
                    risk=f"{i.title} remains {i.status}",
                    impact_severity=(i.severity or "medium").capitalize(),
                    impact=f"{i.repository} · release-blocking",
                    evidence=" · ".join(evidence_bits),
                    refs=sorted(set(linked_refs)),
                )
            )
        for p in security_prs:
            severity = "Medium" if p.security_reviewer_assigned else "High"
            risks.append(
                ReportRisk(
                    risk=(
                        f"Security review is assigned for PR #{p.number}"
                        if p.security_reviewer_assigned
                        else f"Security review remains unassigned for PR #{p.number}"
                    ),
                    impact_severity=severity,
                    impact=f"{p.repository} · {p.title} may miss the release window",
                    evidence=f"PR #{p.number}",
                    refs=refs_for(f"pr-{p.number}"),
                )
            )
        if blocker_thread is not None:
            thread_refs = [
                idx for key, idx in ref.items() if key.startswith("msg-")
            ]
            risks.append(
                ReportRisk(
                    risk="Final release scope is unconfirmed",
                    impact_severity="Medium",
                    impact=f"{blocker_thread.id} readiness decision remains incomplete",
                    evidence=blocker_thread.subject or blocker_thread.id,
                    refs=thread_refs,
                )
            )
        if not risks:
            risks.append(
                ReportRisk(
                    risk="No release blockers detected",
                    impact_severity="Low",
                    impact=f"{project.name} · no open blockers in scope",
                    evidence=", ".join(repo_names) or project.name,
                    refs=[],
                )
            )

        # -------------------------------------------------------- blocker
        release_blocker: Optional[ReportBlocker] = None
        if blocker_issues:
            issue = blocker_issues[0]
            base = re.split(r"\s+block", issue.title, maxsplit=1)[0].strip() or issue.title
            linked_pr = None
            if issue.linked_pr_number:
                linked_pr = next(
                    (p for p in prs if p.number == issue.linked_pr_number), None
                )
            if linked_pr is None and security_prs:
                linked_pr = security_prs[0]
            parts = [f"Issue #{issue.number} remains {issue.status}."]
            blocker_refs = refs_for(f"issue-{issue.number}")
            if linked_pr is not None:
                checks = (
                    "passes checks"
                    if linked_pr.ci_status == "passed"
                    else f"CI is {linked_pr.ci_status}"
                )
                reviewer = (
                    "has an assigned security reviewer"
                    if linked_pr.security_reviewer_assigned
                    else "has no assigned security reviewer"
                )
                parts.append(f"PR #{linked_pr.number} {checks} but {reviewer}.")
                blocker_refs += refs_for(f"pr-{linked_pr.number}")
            if decision_msg is not None:
                parts.append(
                    f"{decision_msg.sender}'s email makes sign-off a mandatory "
                    "release gate."
                )
                blocker_refs += refs_for(f"msg-{decision_msg.id}")
            parts.append(
                "Resolve the review and record approval before merging; do not "
                "interpret passing CI as permission to ship."
            )
            release_blocker = ReportBlocker(
                title=f"{base} security sign-off",
                badge="Blocking",
                description=" ".join(parts) + f" {ranges(sorted(set(blocker_refs)))}",
            )

        # ---------------------------------------------------- github analysis
        issues_by_repo = {name: 0 for name in repo_names}
        prs_by_repo = {name: 0 for name in repo_names}
        for i in issues:
            if i.repository in issues_by_repo:
                issues_by_repo[i.repository] += 1
        for p in prs:
            if p.repository in prs_by_repo:
                prs_by_repo[p.repository] += 1
        all_repos = github_repository.get_repositories()
        all_open = [i for i in github_repository.get_issues() if i.status == "open"]
        active_all = [
            p
            for p in github_repository.get_pull_requests()
            if p.status not in INACTIVE_PR_STATUSES
        ]
        await_review = [
            p
            for p in active_all
            if p.status in ("awaiting_review", "review_pending")
        ]
        ready_to_merge = [p for p in active_all if p.status == "approved"]
        drafts_checks = [
            p for p in active_all if p.status in ("draft", "checks_running")
        ]
        per_repo = ", ".join(
            f"{name} ({issues_by_repo[name]} / {prs_by_repo[name]})"
            for name in repo_names
        )
        github_parts = [
            f"The {len(repo_names)} {project.name} repositories contain "
            f"{len(issues)} open issues and {len(prs)} active pull requests: "
            f"{per_repo}."
        ]
        if security_prs:
            p = security_prs[0]
            github_parts.append(
                f"The highest-impact queue item is PR #{p.number}, "
                f"{p.title.lower()}."
            )
        other_awaiting = next(
            (
                p
                for p in prs
                if p.status in ("awaiting_review", "review_pending")
                and (not security_prs or p.number != security_prs[0].number)
            ),
            None,
        )
        if other_awaiting is not None:
            github_parts.append(
                f"PR #{other_awaiting.number} ({other_awaiting.title}) also awaits review."
            )
        github_parts.append(
            f"Workspace-wide, {len(await_review)} PRs await review, "
            f"{len(ready_to_merge)} are ready to merge, and "
            f"{len(drafts_checks)} are drafts or running checks; "
            f"{len(all_open)} issues are open across {len(all_repos)} repositories."
        )
        github_analysis = " ".join(github_parts)

        # ----------------------------------------------------- gmail analysis
        gmail_parts = [
            f"{len(emails)} relevant emails are scoped to {project.name}."
        ]
        if blocker_thread is not None and thread_messages:
            first = thread_messages[0]
            target = _fmt_date_long(link.target_date) if link and link.target_date else ""
            if target:
                gmail_parts.append(
                    f"In {blocker_thread.id}, {first.sender} confirms {target} "
                    "as the target and asks for scope confirmation."
                )
            else:
                gmail_parts.append(
                    f"In {blocker_thread.id}, {first.sender} sets the release target."
                )
        if decision_msg is not None:
            gmail_parts.append(
                f"{decision_msg.sender} requires security sign-off ({decision_msg.id})."
            )
        for m in extra_decisions[:1]:
            t = thread_by_id.get(m.thread_id)
            sentences = _sentences(m.body, max_n=1)
            when = _fmt_date_long((m.received_at or "")[:10])
            subject = t.subject if t else m.subject
            if sentences:
                gmail_parts.append(
                    f"The {when} {subject} thread: {sentences[0]}"
                )
        if blocker_thread is not None and not any(
            "approv" in (m.body or "").lower() and "not" not in (m.body or "").lower()
            for m in thread_messages
        ):
            gmail_parts.append("Final readiness confirmation is still outstanding.")
        gmail_analysis = " ".join(gmail_parts)

        # ---------------------------------------------- cross-source findings
        findings: List[ReportFinding] = []
        thread_msg_refs = [idx for key, idx in ref.items() if key.startswith("msg-")]
        extra_ref = refs_for(*[k for k in ref if k.startswith("extra-")])
        if blocker_issues and security_prs and decision_msg is not None:
            findings.append(
                ReportFinding(
                    text=(
                        "GitHub's open review gate corroborates Gmail's explicit "
                        "security approval requirement. Together, these support an "
                        f"{(project.status or 'at risk').lower()} assessment."
                    ),
                    refs=sorted(
                        set(
                            refs_for(
                                f"issue-{blocker_issues[0].number}",
                                f"pr-{security_prs[0].number}",
                                f"msg-{decision_msg.id}",
                            )
                        )
                    ),
                )
            )
        if link and link.target_date and thread_messages:
            findings.append(
                ReportFinding(
                    text=(
                        "The email deadline is a target, not an approval. No cited "
                        "record says security review is complete or grants a waiver."
                    ),
                    refs=sorted(
                        set(
                            refs_for("msg-" + thread_messages[0].id)
                            + [idx for key, idx in ref.items() if key.startswith("pr-")]
                        )
                    ),
                )
            )
        if extra_decisions and thread_messages:
            first_ref = refs_for("msg-" + thread_messages[0].id)
            extra_ref = refs_for(f"extra-{extra_decisions[0].id}")
            findings.append(
                ReportFinding(
                    text=(
                        "Scope freeze and scope confirmation are different decisions: "
                        "new endpoints are excluded, but the final release list still "
                        "needs confirmation."
                    ),
                    refs=sorted(set(first_ref + extra_ref)),
                )
            )
        if not findings:
            if link and link.status:
                findings.append(
                    ReportFinding(
                        text=(
                            f"{project.name} cross-source status: {link.status} "
                            f"for {link.target_release}."
                        ),
                        refs=extra_ref[:],
                    )
                )
            for m in priority_emails[:2]:
                if len(findings) >= 2:
                    break
                sentences = _sentences(m.body, max_n=1)
                if not sentences:
                    continue
                key = (
                    f"extra-{m.id}"
                    if f"extra-{m.id}" in ref
                    else (f"msg-{m.id}" if f"msg-{m.id}" in ref else None)
                )
                if key:
                    findings.append(
                        ReportFinding(
                            text=f"{m.sender}: {sentences[0]}", refs=refs_for(key)
                        )
                    )
        findings = findings[:3]

        # ------------------------------------------------------ actions
        actions: List[ReportAction] = []
        due_short = _fmt_date_short(project.target_date)
        tomorrow = due_short
        try:
            d = date.fromisoformat(project.target_date)
            prev = d - timedelta(days=1)
            tomorrow = f"{prev.strftime('%b')} {prev.day}"
        except Exception:  # noqa: BLE001
            tomorrow = due_short
        for p in security_prs:
            if not p.security_reviewer_assigned:
                owner = p.assignee or p.author or project.owner
                actions.append(
                    ReportAction(
                        action=f"Assign security reviewer to PR #{p.number}",
                        owner_due=f"{owner} · Today",
                        evidence=f"PR #{p.number}",
                        refs=sorted(
                            set(
                                refs_for(f"pr-{p.number}")
                                + (
                                    refs_for(f"issue-{blocker_issues[0].number}")
                                    if blocker_issues
                                    else []
                                )
                            )
                        ),
                    )
                )
        if blocker_thread is not None and link and link.target_release:
            owner = thread_messages[0].sender if thread_messages else project.owner
            scope_refs = thread_msg_refs[:]
            if extra_decisions:
                scope_refs += refs_for(f"extra-{extra_decisions[0].id}")
            actions.append(
                ReportAction(
                    action=(
                        f"Confirm {link.target_release} release scope in "
                        f"{blocker_thread.id}"
                    ),
                    owner_due=f"{owner} · Today",
                    evidence=blocker_thread.subject or blocker_thread.id,
                    refs=sorted(set(scope_refs)),
                )
            )
        if security_prs or blocker_thread is not None:
            actions.append(
                ReportAction(
                    action="Re-check readiness after approval",
                    owner_due=f"{project.engineering_lead or project.owner} · {tomorrow}",
                    evidence="Security approval pending",
                    refs=[idx for key, idx in ref.items() if key.startswith("pr-")]
                    or all_indexes(),
                )
            )
        if not actions:
            if link and link.status:
                actions.append(
                    ReportAction(
                        action=f"Record sign-off for {link.target_release}",
                        owner_due=f"{project.release_lead or project.owner} · {due_short}",
                        evidence=link.status,
                        refs=refs_for(*[k for k in ref if k.startswith("extra-")]),
                    )
                )
            else:
                actions.append(
                    ReportAction(
                        action=f"Review release readiness for {project.name}",
                        owner_due=f"{project.owner} · {due_short}",
                        evidence=", ".join(repo_names) or project.name,
                        refs=[],
                    )
                )

        # ------------------------------------------------------- metrics
        open_issues_count = len(issues)
        active_prs_count = len(prs)

        # workspace context (same rules as Evidence Explorer counts)
        ws_issues = github_repository.get_issues()
        ws_prs = github_repository.get_pull_requests()
        ws_threads = gmail_repository.get_threads()
        ws_emails = gmail_repository.get_emails()
        risk_count = (
            len(
                [
                    i
                    for i in ws_issues
                    if i.status == "open"
                    and (i.is_release_blocker or i.severity in ("critical", "high"))
                ]
            )
            + len([p for p in ws_prs if p.status == "awaiting_security_review"])
            + len([t for t in ws_threads if t.is_release_blocker])
        )
        links_all = relationship_repository.get_cross_source_links()
        repos_total = len(all_repos)
        workspace_active = len(active_all)
        workspace_context = (
            f"{repos_total} repositories, {len(all_open)} open issues, "
            f"{workspace_active} active PRs, {len(ws_emails)} emails, "
            f"{risk_count} release-readiness risks, and {len(links_all)} "
            "cross-source decision links"
        )

        # -------------------------------------------- latest agent run
        runs = run_store.list_runs(limit=1)
        run_id = runs[0].get("run_id", "") if runs else ""

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        report_id = f"KO-R{now.strftime('%H%M%S')}"
        report = ReportDocument(
            report_id=report_id,
            project_id=project.id,
            title=f"{project.name} · Release {project.target_release}",
            reporting_period=self._reporting_period(issues, prs, emails),
            generated_at=f"{now.strftime('%B')} {now.day}, {now.year}",
            generated_by=project.owner or "KnowledgeOps AI agent",
            snapshot_time=_snapshot_date(),
            status="Complete",
            executive_summary=executive_summary,
            metrics={
                "health_score": f"{project.health_score} / 100",
                "open_issues": str(open_issues_count),
                "active_prs": str(active_prs_count),
                "relevant_emails": str(len(emails)),
            },
            project_scope=", ".join(repo_names),
            workspace_context=workspace_context,
            major_risks=risks,
            release_blocker=release_blocker,
            github_analysis=github_analysis,
            gmail_analysis=gmail_analysis,
            cross_source_findings=findings,
            recommended_actions=actions,
            evidence_citations=citations,
            provenance=self._provenance(run_id, elapsed_ms),
        )
        self._remember(report)
        return ReportGenerateResponse(report=report, recent=self._recent(project.id))


report_service = ReportService()
