import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.repositories.github_repository import github_repository
from app.repositories.gmail_repository import gmail_repository
from app.repositories.project_repository import project_repository
from app.repositories.relationship_repository import relationship_repository
from app.schemas.dashboard import (
    DashboardAction,
    DashboardActivity,
    DashboardMetrics,
    DashboardOverview,
    DashboardRisk,
)


def _time_only(iso: str) -> str:
    """Source-clock time part: '2026-10-07T09:41:00Z' -> '9:41 AM'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour12}:{dt.strftime('%M')} {ampm}"


def _date_long(d: str) -> str:
    if not d:
        return ""
    try:
        dt = datetime.fromisoformat(d)
    except ValueError:
        return d
    return f"{dt.strftime('%B')} {dt.day}"


def _issue_base(title: str) -> str:
    """'Auth migration blocking release' -> 'Auth migration'."""
    return re.split(r"\s+block", title or "", maxsplit=1)[0].strip() or (title or "")


class DashboardService:
    def get_overview(self) -> DashboardOverview:
        repos = github_repository.get_repositories()
        all_issues = github_repository.get_issues()
        open_issues = [i for i in all_issues if i.status == "open"]
        prs = github_repository.get_pull_requests()
        active_prs = [p for p in prs if p.status not in ("merged", "closed")]
        emails = gmail_repository.get_emails()
        threads = gmail_repository.get_threads()
        projects = project_repository.get_projects()
        links = relationship_repository.get_cross_source_links()

        def project_of(project_id: str):
            return next((p for p in projects if p.id == project_id), None)

        def project_name_of(project_id: str, fallback: str = "") -> str:
            p = project_of(project_id)
            return p.name if p else fallback

        # ---------------------------------------------------------- risks
        risks: List[DashboardRisk] = []

        security_prs = [p for p in prs if p.status == "awaiting_security_review"]
        blocker_threads = [t for t in threads if t.is_release_blocker]
        thread_by_id = {t.id: t for t in threads}
        decision_msg = None
        blocker_thread = blocker_threads[0] if blocker_threads else None
        thread_messages = []
        if blocker_thread is not None:
            thread_messages = sorted(
                gmail_repository.get_emails_by_thread_id(blocker_thread.id),
                key=lambda m: m.received_at or "",
            )
            decision_msg = next(
                (m for m in thread_messages if m.category == "Decision"), None
            )

        for idx, p in enumerate(security_prs, start=1):
            issue = (
                github_repository.get_issue_by_number(p.linked_issue_number)
                if p.linked_issue_number
                else None
            )
            proj = project_of(p.project_id)
            title = (
                f"Security review unassigned for {_issue_base(issue.title).lower()}"
                if issue is not None
                else f"Security review unassigned for PR #{p.number}"
            )
            impact = (
                f"Mandatory release blocker for {proj.target_release} target on "
                f"{_date_long(proj.target_date)}"
                if proj is not None
                else f"{p.repository} · awaiting security review"
            )
            evidence_bits = []
            if issue is not None:
                evidence_bits.append(f"Issue #{issue.number}")
            evidence_bits.append(f"PR #{p.number}")
            if decision_msg is not None:
                n = thread_messages.index(decision_msg) + 1
                evidence_bits.append(f"{blocker_thread.id} Message {n}")
            risks.append(
                DashboardRisk(
                    id=f"risk-sec-{p.number}",
                    title=title,
                    severity="High",
                    project=project_name_of(p.project_id, p.repository),
                    impact=impact,
                    evidence_citation=" · ".join(evidence_bits),
                )
            )

        for link in links:
            if not link.status:
                continue
            proj = project_of(link.project_id)
            name = link.project_name or (proj.name if proj else link.project_id)
            release = link.target_release or (proj.target_release if proj else "")
            evidence_bits = []
            if link.gmail_thread and link.gmail_thread.get("id"):
                evidence_bits.append(f"{link.gmail_thread['id']} Message 1")
            if link.github_pr and link.github_pr.get("number"):
                evidence_bits.append(f"PR #{link.github_pr['number']}")
            if not evidence_bits and link.github_pr:
                evidence_bits.append(str(link.status))
            risks.append(
                DashboardRisk(
                    id=f"risk-link-{link.id}",
                    title=f"{name} approval pending",
                    severity="Medium",
                    project=name,
                    impact=f"{link.status} for {release}; formal sign-off required",
                    evidence_citation=" · ".join(evidence_bits),
                )
            )

        review_queue = [
            p
            for p in active_prs
            if p.status in ("awaiting_review", "review_pending")
        ]
        if review_queue:
            p = max(review_queue, key=lambda x: (x.review_wait_hours or 0))
            risks.append(
                DashboardRisk(
                    id=f"risk-review-{p.number}",
                    title=f"{p.title} awaits review",
                    severity="Medium",
                    project=project_name_of(p.project_id, p.repository),
                    impact=(
                        f"{p.repository} · waiting {p.review_wait_hours}h "
                        "without review"
                    ),
                    evidence_citation=f"PR #{p.number}",
                )
            )

        risks_need_attention = len([r for r in risks if r.severity == "High"])

        # -------------------------------------------------------- actions
        actions: List[DashboardAction] = []

        for p in security_prs:
            proj = project_of(p.project_id)
            issue = (
                github_repository.get_issue_by_number(p.linked_issue_number)
                if p.linked_issue_number
                else None
            )
            subtitle = (
                f"Unblocks the {_issue_base(issue.title).lower()}"
                if issue is not None
                else f"Unblocks {p.title.lower()}"
            )
            evidence_bits = [f"PR #{p.number}"]
            if blocker_thread is not None:
                evidence_bits.append(blocker_thread.id)
            actions.append(
                DashboardAction(
                    id=f"act-sec-{p.number}",
                    title=f"Assign security reviewer to PR #{p.number}",
                    subtitle=subtitle,
                    owner=(proj.owner if proj else "Unassigned"),
                    project=(proj.name if proj else p.repository),
                    due="Today",
                    status="Pending",
                    evidence_citation=" · ".join(evidence_bits),
                )
            )

        scope_link = (
            next((l for l in links if l.project_id == blocker_thread.project_id), None)
            if blocker_thread is not None
            else None
        )
        if blocker_thread is not None and scope_link is not None:
            proj = project_of(blocker_thread.project_id)
            first_sender = thread_messages[0].sender if thread_messages else ""
            release = scope_link.target_release or (
                proj.target_release if proj else ""
            )
            actions.append(
                DashboardAction(
                    id=f"act-scope-{blocker_thread.id}",
                    title=(
                        f"Confirm final {release} scope with {first_sender}"
                        if release
                        else f"Confirm final scope in {blocker_thread.id}"
                    ),
                    subtitle=f"Reply to {blocker_thread.subject}",
                    owner=(proj.owner if proj else first_sender),
                    project=(proj.name if proj else ""),
                    due="Today",
                    status="Pending",
                    evidence_citation=f"{blocker_thread.id} Message 1",
                )
            )

        for link in links:
            if not link.status:
                continue
            proj = project_of(link.project_id)
            name = link.project_name or (proj.name if proj else link.project_id)
            ready = len(
                [
                    p
                    for p in active_prs
                    if p.project_id == link.project_id and p.status == "approved"
                ]
            )
            evidence_bits = []
            if ready:
                evidence_bits.append(f"{ready} pull requests ready to merge")
            if link.gmail_thread and link.gmail_thread.get("id"):
                evidence_bits.append(link.gmail_thread["id"])
            actions.append(
                DashboardAction(
                    id=f"act-qa-{link.id}",
                    title=f"Approve {name} QA sign-off",
                    subtitle=f"{ready} pull requests ready to merge",
                    owner=(proj.owner if proj else "Unassigned"),
                    project=name,
                    due="Today",
                    status="Pending",
                    evidence_citation=" · ".join(evidence_bits) or link.status,
                )
            )

        actions_due_today = len([a for a in actions if a.due == "Today"])

        # ------------------------------------------------- recent activity
        recent_activity: List[DashboardActivity] = []
        if repos:
            synced = max((r.synced_at or "" for r in repos), default="")
            recent_activity.append(
                DashboardActivity(
                    type="github",
                    title="Repositories synchronized",
                    description=(
                        f"{len(repos)} repositories · issues and pull requests indexed"
                    ),
                    timestamp=_time_only(synced),
                )
            )
        if emails:
            latest_recv = max((e.received_at or "" for e in emails), default="")
            if blocker_thread is not None:
                gmail_title = "Release thread added to evidence"
                gmail_desc = (
                    f"{blocker_thread.project_name} · {blocker_thread.subject} · "
                    f"{blocker_thread.message_count} messages"
                )
            else:
                latest = max(emails, key=lambda e: e.received_at or "")
                t = thread_by_id.get(latest.thread_id)
                gmail_title = "Latest email added to evidence"
                gmail_desc = (
                    f"{t.project_name} · {t.subject} · {t.message_count} messages"
                    if t is not None
                    else f"{latest.subject}"
                )
            recent_activity.append(
                DashboardActivity(
                    type="gmail",
                    title=gmail_title,
                    description=gmail_desc,
                    timestamp=_time_only(latest_recv),
                )
            )
        if projects:
            updated = max((p.updated_at or "" for p in projects), default="")
            recent_activity.append(
                DashboardActivity(
                    type="ai",
                    title="Project insights refreshed",
                    description=(
                        f"{len(risks)} risks assessed · {len(actions)} "
                        "recommended actions"
                    ),
                    timestamp=_time_only(updated),
                )
            )

        # -------------------------------------------------------- metrics
        awaiting = [
            p
            for p in active_prs
            if p.status in ("awaiting_review", "review_pending")
        ]
        ready = [p for p in active_prs if p.status == "approved"]
        draft_checks = [
            p for p in active_prs if p.status in ("draft", "checks_running")
        ]
        latest_recv = max((e.received_at or "" for e in emails), default="")
        this_week = 0
        if latest_recv:
            try:
                newest = datetime.fromisoformat(latest_recv.replace("Z", "+00:00"))
                cutoff = newest - timedelta(days=6)
                this_week = len(
                    [
                        e
                        for e in emails
                        if e.received_at
                        and datetime.fromisoformat(e.received_at.replace("Z", "+00:00"))
                    >= cutoff
                    ]
                )
            except ValueError:
                this_week = len(emails)
        orgs = {r.org for r in repos if r.org}

        metrics = DashboardMetrics(
            repositories_count=len(repos),
            open_issues_count=len(open_issues),
            active_prs_count=len(active_prs),
            relevant_emails_count=len(emails),
            project_risks_count=len(risks),
            pending_actions_count=len(actions),
            overall_health="At risk" if risks else "On track",
            overall_health_score=None,
            prs_awaiting_review_count=len(awaiting),
            prs_ready_to_merge_count=len(ready),
            prs_draft_checks_count=len(draft_checks),
            emails_received_this_week=this_week,
            risks_need_attention=risks_need_attention,
            actions_due_today=actions_due_today,
            github_org=next(iter(orgs)) if len(orgs) == 1 else "",
        )

        return DashboardOverview(
            metrics=metrics,
            top_risks=risks,
            pending_actions=actions,
            recent_activity=recent_activity,
        )


dashboard_service = DashboardService()
