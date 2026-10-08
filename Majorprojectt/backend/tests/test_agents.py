import inspect
import sys
from pathlib import Path

import pytest

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.agents.analysis_agent import AnalysisAgent, compose_final_answer
from app.agents.base_agent import BaseAgent
from app.agents.evidence_agent import EvidenceAgent
from app.agents.models import AgentContext
from app.agents.orchestrator import AgentOrchestrator, AgentPipelineError, RunStore
from app.agents.planner_agent import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.workflow_agent import WorkflowAgent
from app.mcp import MCPHealth, MCPHealthReport, MCPProvider, MCPRecord, MockMCPProvider
from app.models.github import Issue, PullRequest
from app.models.gmail import Thread

CRITICAL_QUESTION = "What could delay the Platform API v2.4 release, and what should we do next?"

REQUIRED_OBJECTIVES = [
    "release blockers",
    "authentication migration",
    "open issues",
    "pull requests",
    "security reviews",
    "approval status",
    "release readiness",
    "pending actions",
]


def make_context(question: str = CRITICAL_QUESTION) -> AgentContext:
    return AgentContext(run_id="KO-TEST01", question=question)


def run_pipeline() -> AgentContext:
    context = make_context()
    context = PlannerAgent().run(context)
    context = RetrievalAgent().run(context)
    context = AnalysisAgent().run(context)
    context = WorkflowAgent().run(context)
    context = EvidenceAgent().run(context)
    context.final_answer = compose_final_answer(context)
    return context


# ---------------------------------------------------------------- 1. BaseAgent

class OkAgent(BaseAgent):
    name = "Ok Agent"

    def execute(self, context: AgentContext) -> AgentContext:
        self.detail = "did work"
        return context


class FailingAgent(BaseAgent):
    name = "Failing Agent"

    def execute(self, context: AgentContext) -> AgentContext:
        raise RuntimeError("boom")


def test_base_agent_lifecycle_success():
    agent = OkAgent()
    context = agent.run(make_context())
    assert context is not None
    assert agent.name == "Ok Agent"
    assert agent.status == "completed"
    assert agent.duration_ms >= 0
    assert agent.started_at and agent.ended_at
    assert agent.error is None
    assert agent.detail == "did work"


def test_base_agent_captures_errors():
    agent = FailingAgent()
    with pytest.raises(RuntimeError):
        agent.run(make_context())
    assert agent.status == "failed"
    assert "boom" in agent.error
    assert agent.duration_ms >= 0


# ----------------------------------------------------------- 2. PlannerAgent

def test_planner_identifies_project():
    context = PlannerAgent().run(make_context())
    assert context.project == "Platform API"
    assert context.project_id == "proj-platform-api"


def test_planner_identifies_sources_and_objectives():
    context = PlannerAgent().run(make_context())
    assert set(context.sources) == {"GitHub", "Gmail"}
    assert set(context.record_types) >= {"issues", "pull_requests", "threads"}
    for objective in REQUIRED_OBJECTIVES:
        assert objective in context.retrieval_objectives, f"missing objective: {objective}"


def test_planner_deterministic_time_range():
    context = PlannerAgent().run(make_context("Show release risk for Platform API in the last 7 days"))
    assert context.time_range is not None
    assert "7 days" in context.time_range


# -------------------------------------------------------- 3. RetrievalAgent

def test_retrieval_returns_critical_records():
    context = PlannerAgent().run(make_context())
    context = RetrievalAgent().run(context)
    source_ids = {r.source_id for r in context.retrieved_records}
    assert "Issue #142" in source_ids
    assert "PR #284" in source_ids
    assert "GM-064" in source_ids
    for record in context.retrieved_records:
        assert record.source
        assert record.record_type
        assert record.source_id
        assert record.project_id == "proj-platform-api"


def test_retrieval_uses_mcp_provider_interface():
    class FakeMCP(MCPProvider):
        provider_name = "fake"

        def search_github(self, query="", project_id="", kind="issues", limit=10):
            if kind == "issues":
                issue = Issue(id=1, number=1, title="T", repository="r",
                              project_id=project_id, is_release_blocker=True)
                return [MCPRecord(source="GitHub", record_type="issue",
                                  source_id="Issue #1", project_id=project_id,
                                  data=issue.model_dump())]
            if kind == "pull_requests":
                pr = PullRequest(id=2, number=2, title="T", repository="r",
                                 project_id=project_id)
                return [MCPRecord(source="GitHub", record_type="pull_request",
                                  source_id="PR #2", project_id=project_id,
                                  data=pr.model_dump())]
            return []

        def search_gmail(self, query="", project_id="", kind="threads", thread_id="", limit=10):
            if kind == "threads":
                thread = Thread(id="GM-1", subject="S", project_id=project_id,
                                is_release_blocker=True)
                return [MCPRecord(source="Gmail", record_type="thread",
                                  source_id="GM-1", project_id=project_id,
                                  data=thread.model_dump())]
            return []

        def get_github_repository(self, repository_id):
            return None

        def get_github_issue(self, number):
            return None

        def get_github_pull_request(self, number):
            return None

        def get_github_commit(self, sha):
            return None

        def get_github_review(self, review_id):
            return None

        def get_gmail_thread(self, thread_id):
            return None

        def get_gmail_message(self, message_id):
            return None

        def get_cross_source_links(self, project_id=""):
            return []

        def health_check(self):
            return MCPHealthReport(provider="fake",
                                   github=MCPHealth(server="github"),
                                   gmail=MCPHealth(server="gmail"))

        def github_health(self):
            return MCPHealth(server="github")

        def gmail_health(self):
            return MCPHealth(server="gmail")

    context = PlannerAgent().run(make_context())
    context = RetrievalAgent(provider=FakeMCP()).run(context)
    source_ids = {r.source_id for r in context.retrieved_records}
    assert source_ids == {"Issue #1", "PR #2", "GM-1"}


def test_retrieval_depends_on_mcp_provider_seam():
    assert issubclass(MockMCPProvider, MCPProvider)
    agent_source = inspect.getsource(sys.modules["app.agents.retrieval_agent"])
    assert "MCPProvider" in agent_source
    assert "get_mcp_provider" in agent_source
    assert "app.repositories" not in agent_source
    assert "json.load" not in agent_source


# --------------------------------------------------------- 4. AnalysisAgent

def test_analysis_identifies_risks_and_blockers():
    context = run_pipeline()
    assert context.release_status == "At risk"
    assert any("Issue #142" in b for b in context.blockers)
    assert any("PR #284" in b and "Security reviewer" in b for b in context.blockers)
    assert any("Security review remains unassigned for PR #284" in r for r in context.risks)
    assert any("release scope" in r.lower() for r in context.risks)


def test_analysis_identifies_decisions_and_approval_gate():
    context = run_pipeline()
    assert any("Security approval is a mandatory release gate" in d for d in context.decisions)
    assert any("target release date" in d for d in context.decisions)
    assert any("PR #284 is the approval gate" in d for d in context.decisions)


def test_analysis_claims_distinguish_facts_from_inference():
    context = run_pipeline()
    claims = {c.claim for c in context.claims}
    assert "Authentication migration is release-blocking." in claims
    assert "PR #284 requires security review." in claims
    assert "Security approval is mandatory before release." in claims
    assert context.confidence == "high"
    assert any("at risk" in i for i in context.inferences)
    assert any("not a confirmed delay" in i for i in context.inferences)
    assert any("passed CI checks" in f for f in context.facts)
    assert context.contradictions, "expected CI-passed vs security-review contradiction"


def test_final_answer_distinguishes_at_risk_from_confirmed_delay():
    context = run_pipeline()
    answer = context.final_answer.lower()
    assert "currently at risk" in answer
    assert "release-blocking" in answer
    assert "pr #284" in answer
    assert "gm-064" in answer
    assert "will definitely" not in answer
    assert "confirmed delay" not in answer
    assert "will be delayed" not in answer


# --------------------------------------------------------- 5. WorkflowAgent

def test_workflow_creates_three_recommended_actions():
    context = run_pipeline()
    assert context.recommended_actions == [
        "Assign a security reviewer for PR #284",
        "Confirm the remaining release scope",
        "Recheck release readiness after security approval",
    ]


def test_workflow_actions_have_owners_and_dependencies():
    context = run_pipeline()
    details = context.action_details
    assert details[0].owner == "Priya Rao"  # project security lead
    assert details[0].priority == 1
    assert details[2].depends_on == [
        "Assign a security reviewer for PR #284",
        "Confirm the remaining release scope",
    ]
    assert all(a.status == "draft" for a in details)


def test_workflow_agent_performs_no_external_actions():
    source = inspect.getsource(__import__("app.agents.workflow_agent", fromlist=["x"]))
    for forbidden in ("import requests", "import httpx", "import urllib", "import smtplib", "import ftplib"):
        assert forbidden not in source


# --------------------------------------------------------- 6. EvidenceAgent

def test_evidence_links_three_claims_to_source_records():
    context = run_pipeline()
    labels = [e.label for e in context.evidence]
    assert "GitHub Issue #142" in labels
    assert "GitHub PR #284" in labels
    assert "Gmail Thread GM-064" in labels
    assert len(context.evidence) == 3


def test_evidence_only_uses_existing_records():
    context = run_pipeline()
    retrieved_ids = {r.source_id for r in context.retrieved_records}
    for ref in context.evidence:
        assert ref.source_id in retrieved_ids, f"fabricated evidence: {ref.source_id}"
        assert ref.source
        assert ref.record_type
        assert ref.project_id == "proj-platform-api"
        assert ref.title
        assert ref.relevant_information
        assert ref.claim
    pr_evidence = next(e for e in context.evidence if e.source_id == "PR #284")
    assert "Issue #142" in pr_evidence.relationship_information
    assert [e.citation_id for e in context.evidence] == ["1", "2", "3"]


# ------------------------------------------------------- 7. AgentOrchestrator

def test_orchestrator_executes_full_pipeline_in_order():
    store = RunStore()
    context = AgentOrchestrator().run(CRITICAL_QUESTION, store=store)
    assert context.run_id.startswith("KO-")
    assert context.run_status == "completed"
    names = [s.agent for s in context.execution_trace]
    assert names == [
        "Planner Agent",
        "Retrieval Agent",
        "Analysis Agent",
        "LLM Agent",
        "Workflow Agent",
        "Evidence Agent",
    ]
    for stage in context.execution_trace:
        assert stage.status == "completed"
        assert stage.duration_ms >= 0  # real measured duration, no artificial delays
        assert stage.started_at and stage.ended_at
        assert stage.error is None
    assert context.total_duration_ms >= 0
    assert context.ended_at
    saved = store.get(context.run_id)
    assert saved is not None
    assert saved["status"] == "completed"
    assert len(store.list_runs()) == 1


def test_orchestrator_generates_unique_run_ids():
    store = RunStore()
    first = AgentOrchestrator().run(CRITICAL_QUESTION, store=store)
    second = AgentOrchestrator().run(CRITICAL_QUESTION, store=store)
    assert first.run_id != second.run_id
    assert len(store.list_runs()) == 2
    assert store.list_runs()[0]["run_id"] == second.run_id  # newest first


def test_orchestrator_captures_failure_and_skips_dependents():
    store = RunStore()
    orchestrator = AgentOrchestrator(agents=[OkAgent(), FailingAgent(), OkAgent()])
    with pytest.raises(AgentPipelineError) as excinfo:
        orchestrator.run("any question", store=store)
    error = excinfo.value
    assert error.run_id.startswith("KO-")
    assert error.failed_stage == "Failing Agent"
    statuses = [s.status for s in error.trace]
    assert statuses == ["completed", "failed", "skipped"]
    failed_trace = [s for s in error.trace if s.status == "failed"][0]
    assert "boom" in failed_trace.error
    saved = store.get(error.run_id)
    assert saved is not None
    assert saved["status"] == "failed"
    assert saved["failed_stage"] == "Failing Agent"
    assert saved["error"] == "boom"
