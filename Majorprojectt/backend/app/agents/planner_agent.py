import re
from typing import List, Optional

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentContext
from app.repositories.project_repository import project_repository

# Deterministic keyword rules: question token -> retrieval objective.
OBJECTIVE_RULES = [
    (r"\b(delay|blocker|blocked|blocking|risk|at risk|slip)\b", "release blockers"),
    (r"\b(auth|authentication)\b", "authentication migration"),
    (r"\bissue(s)?\b", "open issues"),
    (r"\bpull request(s)?\b|\bpr\s*#?\d*\b", "pull requests"),
    (r"\bsecurity review(s)?\b|\breview(s)?\b", "security reviews"),
    (r"\bapprov(e|al|ed|ing)\b|\bsign-?off\b", "approval status"),
    (r"\breadiness|ready to (ship|release)|\bship\b", "release readiness"),
    (r"\bnext steps?\b|\bwhat should we do\b|\baction(s)?\b|\btodo\b", "pending actions"),
]

# A release-risk question gets the full release-readiness objective template.
RELEASE_RISK_PATTERN = r"\b(delay|blocker|blocked|risk|at risk|ready|ship|launch)\b.*\brelease\b|\brelease\b.*\b(delay|blocker|risk|ready)\b"

RELEASE_RISK_TEMPLATE = [
    "release blockers",
    "open issues",
    "pull requests",
    "security reviews",
    "approval status",
    "release readiness",
    "pending actions",
]

SOURCE_RULES = {
    "GitHub": [r"\bgithub\b", r"\bissue(s)?\b", r"\bpull request(s)?\b", r"\bpr\s*#?\d*\b", r"\bcommit(s)?\b", r"\brepo(sitorie)?s?\b"],
    "Gmail": [r"\bgmail\b", r"\bemail(s)?\b", r"\bthread(s)?\b", r"\binbox\b", r"\bmessage(s)?\b"],
}

RECORD_TYPES_BY_SOURCE = {
    "GitHub": ["issues", "pull_requests"],
    "Gmail": ["threads", "emails"],
}

TIME_RANGE_PATTERNS = [
    r"\blast \d+ days?\b",
    r"\bthis (week|month)\b",
    r"\bnext \d+ days?\b",
    r"\bby [A-Z][a-z]+ \d{1,2}\b",
    r"\b[A-Z][a-z]+ \d{1,2}\b",
]


class PlannerAgent(BaseAgent):
    """Identifies project, sources, record types, retrieval objectives and time range."""

    name = "Planner Agent"

    def execute(self, context: AgentContext) -> AgentContext:
        question = context.question.lower()

        project = self._identify_project(context.question)
        if project is not None:
            context.project = project.name
            context.project_id = project.id
            context.target_release = project.target_release
            context.target_date = project.target_date

        context.sources = self._identify_sources(question)
        context.record_types = self._identify_record_types(context.sources)
        context.retrieval_objectives = self._identify_objectives(question, project)
        context.time_range = self._identify_time_range(context.question)

        self.detail = (
            f"project={context.project or 'unspecified'} · "
            f"{len(context.retrieval_objectives)} objectives · "
            f"sources={', '.join(context.sources) or 'none'}"
        )
        return context

    def _identify_project(self, question: str):
        projects = project_repository.get_projects()
        question_lower = question.lower()
        for project in projects:
            if project.name.lower() in question_lower:
                return project
        # Fallback: match a release tag mentioned in the question (e.g. "v2.4").
        for project in projects:
            if project.target_release and project.target_release.lower() in question_lower:
                return project
        return None

    def _identify_sources(self, question_lower: str) -> List[str]:
        sources: List[str] = []
        for source, patterns in SOURCE_RULES.items():
            if any(re.search(pattern, question_lower) for pattern in patterns):
                sources.append(source)
        # No explicit source mentioned -> the whole workspace is in scope.
        return sources if sources else ["GitHub", "Gmail"]

    def _identify_record_types(self, sources: List[str]) -> List[str]:
        record_types: List[str] = []
        for source in sources:
            for record_type in RECORD_TYPES_BY_SOURCE.get(source, []):
                if record_type not in record_types:
                    record_types.append(record_type)
        return record_types

    def _identify_objectives(self, question_lower: str, project) -> List[str]:
        keyword_objectives: List[str] = []
        for pattern, objective in OBJECTIVE_RULES:
            if re.search(pattern, question_lower) and objective not in keyword_objectives:
                keyword_objectives.append(objective)

        # Release-risk questions use the standard release-readiness template.
        if re.search(RELEASE_RISK_PATTERN, question_lower, re.DOTALL):
            project_text = f"{project.description} {project.name}".lower() if project else ""
            objectives: List[str] = []
            for objective in RELEASE_RISK_TEMPLATE:
                if objective not in objectives:
                    objectives.append(objective)
            # "authentication migration" only applies when the project involves auth work.
            if "auth" in project_text or "migration" in project_text:
                objectives.insert(1, "authentication migration")
            for objective in keyword_objectives:
                if objective not in objectives:
                    objectives.append(objective)
            return objectives

        return keyword_objectives

    def _identify_time_range(self, question: str) -> Optional[str]:
        for pattern in TIME_RANGE_PATTERNS:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return match.group(0)
        return None
