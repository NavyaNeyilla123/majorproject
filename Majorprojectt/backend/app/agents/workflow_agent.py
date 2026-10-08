from typing import List

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentContext, RecommendedAction


class WorkflowAgent(BaseAgent):
    """Converts analysis into prioritized draft recommendations.

    Draft-only: this agent never modifies GitHub, never approves or merges PRs,
    never sends or modifies Gmail, and performs no external actions.
    """

    name = "Workflow Agent"

    def execute(self, context: AgentContext) -> AgentContext:
        actions: List[RecommendedAction] = []

        security_prs = [
            r for r in context.retrieved_records
            if r.record_type == "pull_request"
            and r.data.get("status") == "awaiting_security_review"
            and not r.data.get("security_reviewer_assigned")
        ]
        scope_pending = any("Confirm the remaining release scope" == a for a in context.unresolved_actions)
        scope_pending = scope_pending or any(
            "confirm" in r.summary.lower()
            for r in context.retrieved_records
            if r.record_type == "thread" and r.data.get("is_release_blocker")
        )

        for record in security_prs:
            number = record.data.get("number")
            actions.append(
                RecommendedAction(
                    action=f"Assign a security reviewer for PR #{number}",
                    priority=1,
                    owner=self._owner(context, "security_lead", record.data.get("assignee")),
                    owner_source="project security lead / PR assignment",
                    depends_on=[],
                    evidence_source_ids=[record.source_id],
                )
            )

        if scope_pending:
            thread = next(
                (r for r in context.retrieved_records if r.record_type == "thread" and r.data.get("is_release_blocker")),
                None,
            )
            actions.append(
                RecommendedAction(
                    action="Confirm the remaining release scope",
                    priority=2,
                    owner=self._owner(context, "release_lead"),
                    owner_source="project release lead",
                    depends_on=[],
                    evidence_source_ids=[thread.source_id] if thread else [],
                )
            )

        if security_prs:
            prior = [a.action for a in actions]
            thread = next(
                (r for r in context.retrieved_records if r.record_type == "thread" and r.data.get("is_release_blocker")),
                None,
            )
            actions.append(
                RecommendedAction(
                    action="Recheck release readiness after security approval",
                    priority=3,
                    owner=self._owner(context, "release_lead"),
                    owner_source="project release lead",
                    depends_on=prior,
                    evidence_source_ids=[r.source_id for r in security_prs] + ([thread.source_id] if thread else []),
                )
            )

        # Fallback: draft actions from unresolved analysis items.
        if not actions:
            for index, unresolved in enumerate(context.unresolved_actions[:3], start=1):
                actions.append(
                    RecommendedAction(
                        action=unresolved.split(": ", 1)[-1],
                        priority=index,
                        owner="",
                        depends_on=[],
                        evidence_source_ids=[],
                    )
                )

        actions.sort(key=lambda a: a.priority)
        context.action_details = actions
        context.recommended_actions = [a.action for a in actions]
        self.detail = f"{len(actions)} actions drafted (draft only, no external actions)"
        return context

    def _owner(self, context: AgentContext, role: str, fallback: str = "") -> str:
        from app.repositories.project_repository import project_repository

        project = project_repository.get_project_by_id(context.project_id) if context.project_id else None
        if project is not None:
            owner = getattr(project, role, "") or ""
            if owner:
                return owner
        return fallback or ""
