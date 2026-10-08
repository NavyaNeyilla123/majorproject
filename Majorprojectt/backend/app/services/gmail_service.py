import re
from datetime import datetime, timedelta
from typing import List, Optional

from app.repositories.gmail_repository import gmail_repository
from app.schemas.gmail import (
    GmailStats, GmailOverviewResponse,
    ExtractedDecision, ExtractedRisk, ExtractedAction
)
from app.models.gmail import Thread, Email


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    return parts[0]


def _second_sentence(text: str) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=2)
    return parts[1] if len(parts) > 1 else ""


def _title_text(text: str) -> str:
    """First sentence, widened when too short to stand alone as a title."""
    if not text:
        return ""
    first = _first_sentence(text)
    if len(first) >= 15:
        return first
    parts = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=2)
    return " ".join(parts[:2]) if len(parts) > 1 else first


def _fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


class GmailService:
    def get_overview(self) -> GmailOverviewResponse:
        threads = gmail_repository.get_threads()
        emails = gmail_repository.get_emails()
        thread_by_id = {t.id: t for t in threads}
        priority_threads = [t for t in threads if t.category == "Risk" or t.is_release_blocker]

        this_week = 0
        received = [e.received_at for e in emails if e.received_at]
        if received:
            newest = max(received)
            try:
                cutoff = datetime.fromisoformat(newest.replace("Z", "+00:00")) - timedelta(days=6)
                this_week = len([
                    e for e in emails
                    if e.received_at
                    and datetime.fromisoformat(e.received_at.replace("Z", "+00:00")) >= cutoff
                ])
            except ValueError:
                this_week = len(emails)

        stats = GmailStats(
            relevant_email_count=len(emails),
            emails_received_this_week=this_week,
            project_risks_count=len(priority_threads),
            priority_threads_count=len(priority_threads)
        )

        decision_emails = sorted(
            [e for e in emails if e.category == "Decision"],
            key=lambda e: e.received_at or "",
        )
        decisions = [
            ExtractedDecision(
                id=f"dec-{n}",
                decision=_title_text(e.body),
                source_thread=e.thread_id,
                owner=e.sender,
                date=_fmt_date(e.received_at),
            )
            for n, e in enumerate(decision_emails, start=1)
        ]

        risk_emails = sorted(
            [e for e in emails if e.category == "Risk"],
            key=lambda e: e.received_at or "",
        )
        risks = []
        for n, e in enumerate(risk_emails, start=1):
            thread = thread_by_id.get(e.thread_id)
            severity = "High" if (thread is not None and thread.is_release_blocker) else "Medium"
            impact = _second_sentence(e.body) or _first_sentence(e.body)
            risks.append(
                ExtractedRisk(
                    id=f"risk-{n}",
                    risk=_title_text(e.body),
                    severity=severity,
                    source_thread=e.thread_id,
                    impact=impact,
                )
            )

        action_emails = sorted(
            [e for e in emails if e.category == "Action"],
            key=lambda e: e.received_at or "",
        )
        actions = []
        for n, e in enumerate(action_emails, start=1):
            due = "Today" if re.search(r"\btoday\b", e.body or "", re.IGNORECASE) else "Not specified"
            actions.append(
                ExtractedAction(
                    id=f"act-{n}",
                    action=_title_text(e.body),
                    owner=e.sender,
                    due=due,
                    source_thread=e.thread_id,
                )
            )

        return GmailOverviewResponse(
            stats=stats,
            threads=threads,
            emails=emails,
            extracted_decisions=decisions,
            extracted_risks=risks,
            extracted_actions=actions,
        )

    def get_threads(self) -> List[Thread]:
        return gmail_repository.get_threads()

    def get_thread_by_id(self, thread_id: str) -> Optional[Thread]:
        return gmail_repository.get_thread_by_id(thread_id)

    def get_emails(self) -> List[Email]:
        return gmail_repository.get_emails()


gmail_service = GmailService()
