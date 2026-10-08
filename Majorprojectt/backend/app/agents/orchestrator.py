import time
import uuid
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence

from app.agents.analysis_agent import AnalysisAgent, compose_final_answer
from app.agents.base_agent import BaseAgent, utc_now_iso
from app.agents.evidence_agent import EvidenceAgent
from app.agents.llm_agent import LLMAgent
from app.agents.models import AgentContext, TraceStage
from app.agents.planner_agent import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.workflow_agent import WorkflowAgent

MAX_STORED_RUNS = 50


class AgentPipelineError(Exception):
    """Raised when a stage fails; carries run_id so the failed run stays inspectable."""

    def __init__(self, run_id: str, failed_stage: str, message: str, trace: List[TraceStage]) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.failed_stage = failed_stage
        self.message = message
        self.trace = trace


class RunStore:
    """In-memory store of recent agent runs (bounded; reset on process restart)."""

    def __init__(self, max_runs: int = MAX_STORED_RUNS) -> None:
        self.max_runs = max_runs
        self._runs: "OrderedDict[str, Dict]" = OrderedDict()

    def save(self, snapshot: Dict) -> None:
        run_id = snapshot.get("run_id", "")
        self._runs[run_id] = snapshot
        self._runs.move_to_end(run_id)
        while len(self._runs) > self.max_runs:
            self._runs.popitem(last=False)

    def get(self, run_id: str) -> Optional[Dict]:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 20) -> List[Dict]:
        runs = list(self._runs.values())[::-1]
        return runs[: max(limit, 0)]

    def clear(self) -> None:
        self._runs.clear()


run_store = RunStore()


def build_run_snapshot(context: AgentContext) -> Dict:
    return {
        "run_id": context.run_id,
        "question": context.question,
        "project": context.project,
        "project_id": context.project_id,
        "status": context.run_status,
        "started_at": context.started_at,
        "ended_at": context.ended_at,
        "total_duration_ms": context.total_duration_ms,
        "stages": [stage.model_dump() for stage in context.execution_trace],
        "actions_awaiting_count": len(context.recommended_actions),
        "answer": context.final_answer,
        "confidence": context.confidence,
        "target_release": context.target_release,
        "target_date": context.target_date,
        "release_status": context.release_status,
        "risks": list(context.risks),
        "blockers": list(context.blockers),
        "decisions": list(context.decisions),
        "unresolved_actions": list(context.unresolved_actions),
        "contradictions": list(context.contradictions),
        "recommended_actions": list(context.recommended_actions),
        "action_details": [action.model_dump() for action in context.action_details],
        "evidence": [ref.model_dump() for ref in context.evidence],
        "sources": [ref.label for ref in context.evidence],
        "llm_used": context.llm_used,
        "failed_stage": context.failed_stage,
        "error": context.error,
    }


class AgentOrchestrator:
    """Runs Planner -> Retrieval -> Analysis -> LLM -> Workflow -> Evidence in order."""

    def __init__(self, agents: Optional[Sequence[BaseAgent]] = None) -> None:
        self.agents: List[BaseAgent] = list(agents) if agents is not None else [
            PlannerAgent(),
            RetrievalAgent(),
            AnalysisAgent(),
            LLMAgent(),
            WorkflowAgent(),
            EvidenceAgent(),
        ]

    def run(self, question: str, store: Optional[RunStore] = None) -> AgentContext:
        store = store if store is not None else run_store
        run_id = f"KO-{uuid.uuid4().hex[:8].upper()}"
        context = AgentContext(run_id=run_id, question=question, started_at=utc_now_iso())
        stages: List[TraceStage] = []
        failed_stage: Optional[str] = None
        failure_message: Optional[str] = None
        pipeline_start = time.perf_counter()

        for agent in self.agents:
            if failed_stage is not None:
                stages.append(
                    TraceStage(
                        agent=agent.name,
                        status="skipped",
                        duration_ms=0.0,
                        started_at="",
                        ended_at="",
                        detail="skipped: an earlier stage failed",
                    )
                )
                continue
            try:
                context = agent.run(context)
                stages.append(
                    TraceStage(
                        agent=agent.name,
                        status="completed",
                        duration_ms=agent.duration_ms,
                        started_at=agent.started_at,
                        ended_at=agent.ended_at,
                        detail=agent.detail,
                    )
                )
            except Exception as exc:
                failed_stage = agent.name
                failure_message = str(exc) or exc.__class__.__name__
                stages.append(
                    TraceStage(
                        agent=agent.name,
                        status="failed",
                        duration_ms=agent.duration_ms,
                        started_at=agent.started_at,
                        ended_at=agent.ended_at,
                        detail=agent.detail,
                        error=failure_message,
                    )
                )

        context.execution_trace = stages
        context.total_duration_ms = round((time.perf_counter() - pipeline_start) * 1000, 3)
        context.ended_at = utc_now_iso()

        if failed_stage is not None:
            context.run_status = "failed"
            context.failed_stage = failed_stage
            context.error = failure_message
            store.save(build_run_snapshot(context))
            raise AgentPipelineError(run_id, failed_stage, failure_message or "agent failed", stages)

        if not context.final_answer:
            context.final_answer = compose_final_answer(context)
        context.run_status = "completed"
        store.save(build_run_snapshot(context))
        return context
