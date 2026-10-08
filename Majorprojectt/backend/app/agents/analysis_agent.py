import calendar
import re
from typing import List

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentContext, AnalysisClaim, RetrievedRecord

FORBIDDEN_CLAIM_PHRASES = ["will definitely", "confirmed delay", "will be delayed"]


def normalize_release_terms(text: str) -> str:
    """Deterministic readability normalization (no LLM): 'auth migration' -> 'authentication migration'."""
    return re.sub(r"\bauth migration\b", "authentication migration", text, flags=re.IGNORECASE)


def blocker_core(title: str) -> str:
    core = re.sub(r"\s*block(ing|s)?\s*(the\s+)?release\s*", " ", title, flags=re.IGNORECASE)
    core = re.sub(r"\s+", " ", core).strip(" -,.:;!")
    core = normalize_release_terms(core)
    return core.lower() if core else "change"


def format_target_date(iso_date: str, with_year: bool = False) -> str:
    try:
        year, month, day = [int(part) for part in iso_date.split("-")]
        month_name = calendar.month_name[month]
        return f"{month_name} {day}, {year}" if with_year else f"{month_name} {day}"
    except (ValueError, AttributeError):
        return iso_date


def compose_final_answer(context: AgentContext) -> str:
    """Builds the final answer from retrieved records. At risk != confirmed delay."""
    issue_blockers = [
        r for r in context.retrieved_records
        if r.record_type == "issue" and r.data.get("is_release_blocker") and r.data.get("status") == "open"
    ]
    pr_blockers = [
        r for r in context.retrieved_records
        if r.record_type == "pull_request"
        and r.data.get("status") == "awaiting_security_review"
        and not r.data.get("security_reviewer_assigned")
    ]
    approval_threads = [
        r for r in context.retrieved_records
        if r.record_type == "thread"
        and r.data.get("is_release_blocker")
        and "approval" in f"{r.title} {r.summary}".lower()
    ]

    clauses: List[str] = []
    if issue_blockers:
        clauses.append(f"the {blocker_core(issue_blockers[0].title)} is release-blocking")
    if pr_blockers:
        clauses.append(f"PR #{pr_blockers[0].data.get('number')} still requires security review")
    if not clauses and approval_threads:
        clauses.append("security approval for the release is still pending")
    if not clauses and context.blockers:
        clauses.append(context.blockers[0])

    project = context.project or "project"
    release = f" {context.target_release}" if context.target_release else ""
    if clauses:
        if len(clauses) == 1:
            reason = clauses[0]
        else:
            reason = f"{', '.join(clauses[:-1])} and {clauses[-1]}"
        answer = f"The {project}{release} release is currently at risk because {reason}."
    else:
        answer = f"No release-blocking evidence was found for the {project}{release} release in the retrieved records."

    if approval_threads:
        thread_id = approval_threads[0].data.get("id", "")
        answer += f" Gmail thread {thread_id} confirms that security approval is required before release."

    for phrase in FORBIDDEN_CLAIM_PHRASES:
        if phrase in answer.lower():
            answer = answer.replace(phrase, "is assessed as at risk (not confirmed)")
    return answer


class AnalysisAgent(BaseAgent):
    """Correlates retrieved records into risks, blockers, decisions and claims."""

    name = "Analysis Agent"

    def execute(self, context: AgentContext) -> AgentContext:
        records = context.retrieved_records
        cross_links = [r for r in records if r.record_type == "cross_source_link"]

        for record in records:
            if record.record_type == "issue":
                self._analyze_issue(context, record)
            elif record.record_type == "pull_request":
                self._analyze_pull_request(context, record)
            elif record.record_type == "thread":
                self._analyze_thread(context, record)

        self._analyze_cross_links(context, cross_links)
        self._derive_overall_assessment(context)
        self._determine_confidence(context)
        for claim in context.claims:
            claim.confidence = context.confidence

        self.detail = (
            f"{len(context.risks)} risks · {len(context.blockers)} blockers · "
            f"{len(context.decisions)} decisions"
        )
        return context

    def _analyze_issue(self, context: AgentContext, record: RetrievedRecord) -> None:
        data = record.data
        if data.get("is_release_blocker") and data.get("status") == "open":
            context.blockers.append(f"{record.source_id}: {data.get('title', record.title)}")
            claim = f"{blocker_core(record.title).capitalize()} is release-blocking."
            self._add_claim(context, claim, "blocker", [record.source_id])
            context.facts.append(f"{record.source_id} is marked release-blocking: {record.title}")
            if data.get("body"):
                context.facts.append(f"{record.source_id} body: {data['body']}")
        elif data.get("status") == "open" and data.get("severity") in ("critical", "high"):
            context.risks.append(f"Open {data.get('severity')} severity issue {record.source_id}: {data.get('title', record.title)}")

    def _analyze_pull_request(self, context: AgentContext, record: RetrievedRecord) -> None:
        data = record.data
        number = data.get("number")
        if data.get("status") == "awaiting_security_review" and not data.get("security_reviewer_assigned"):
            context.blockers.append(f"PR #{number}: Security reviewer unassigned")
            context.risks.append(
                f"Security review remains unassigned for PR #{number} ({data.get('title', record.title)})"
            )
            self._add_claim(context, f"PR #{number} requires security review.", "blocker", [record.source_id])
            if data.get("ci_status") == "passed":
                context.facts.append(f"PR #{number} has passed CI checks.")
                context.contradictions.append(
                    f"PR #{number} passed CI checks but is still awaiting security review; passing checks is not release approval."
                )
            context.facts.append(
                f"PR #{number} status: {data.get('status')}; security reviewer assigned: {bool(data.get('security_reviewer_assigned'))}"
            )
        next_step = (data.get("next_step") or "").strip()
        if next_step and data.get("status") not in ("approved", "merged"):
            unresolved = f"PR #{number}: {next_step}"
            if unresolved not in context.unresolved_actions:
                context.unresolved_actions.append(unresolved)

    def _analyze_thread(self, context: AgentContext, record: RetrievedRecord) -> None:
        data = record.data
        text = f"{record.title} {record.summary}".lower()
        if not data.get("is_release_blocker"):
            return
        if "approval" in text and any(word in text for word in ("required", "mandatory", "sign-off", "signoff")):
            context.decisions.append("Security approval is a mandatory release gate.")
            self._add_claim(
                context,
                "Security approval is mandatory before release.",
                "decision",
                [record.source_id],
            )
            context.facts.append(f"Gmail {record.source_id}: {record.summary}")
        if "confirm" in text:
            risk = f"Final release scope for {context.target_release or 'the release'} remains unconfirmed"
            if risk not in context.risks:
                context.risks.append(risk)

    def _analyze_cross_links(self, context: AgentContext, cross_links: List[RetrievedRecord]) -> None:
        for record in cross_links:
            data = record.data
            target_date = data.get("target_date") or context.target_date
            if target_date:
                decision = f"{format_target_date(target_date)} is the target release date."
                if decision not in context.decisions:
                    context.decisions.append(decision)
            blocker = data.get("primary_blocker") or {}
            github_pr = blocker.get("github_pr") or {}
            if github_pr.get("number"):
                decision = f"PR #{github_pr['number']} is the approval gate for this release."
                if decision not in context.decisions:
                    context.decisions.append(decision)
            for fact in data.get("provenance_facts", []):
                if fact not in context.facts:
                    context.facts.append(fact)
            for fact in data.get("provenance_facts", []):
                if "confirm release scope" in fact.lower():
                    action = "Confirm the remaining release scope"
                    if action not in context.unresolved_actions:
                        context.unresolved_actions.append(action)

    def _derive_overall_assessment(self, context: AgentContext) -> None:
        if context.blockers:
            context.release_status = "At risk"
            context.inferences.append(
                f"The {context.project} {context.target_release} release is at risk."
            )
            context.inferences.append(
                "Assessment: at risk, not a confirmed delay. No evidence establishes that the release will be delayed."
            )
        else:
            context.release_status = "No release blockers found"

    def _determine_confidence(self, context: AgentContext) -> None:
        substantive = [r for r in context.retrieved_records if r.record_type != "cross_source_link"]
        sources = {r.source for r in substantive}
        if len(substantive) >= 3 and len(sources) >= 2:
            context.confidence = "high"
        elif substantive:
            context.confidence = "medium"
        else:
            context.confidence = "low"

    def _add_claim(self, context: AgentContext, claim: str, kind: str, source_ids: List[str]) -> None:
        for existing in context.claims:
            if existing.claim == claim:
                return
        context.claims.append(
            AnalysisClaim(claim=claim, kind=kind, confidence=context.confidence or "medium", source_ids=source_ids)
        )
