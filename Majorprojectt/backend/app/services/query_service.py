from app.agents.analysis_agent import format_target_date
from app.agents.orchestrator import AgentOrchestrator
from app.schemas.query import QueryRequest, QueryResponse

class QueryService:
    """Executes POST /api/query through the multi-agent orchestrator."""

    def __init__(self) -> None:
        self.orchestrator = AgentOrchestrator()

    def process_query(self, request: QueryRequest) -> QueryResponse:
        context = self.orchestrator.run(request.question)
        return QueryResponse(
            run_id=context.run_id,
            question=context.question,
            answer=context.final_answer,
            project=context.project,
            target_release=context.target_release,
            target_date=format_target_date(context.target_date, with_year=True),
            status=context.release_status,
            confidence=context.confidence,
            risks=context.risks,
            blockers=context.blockers,
            decisions=context.decisions,
            recommended_actions=context.recommended_actions,
            action_details=context.action_details,
            evidence=context.evidence,
            sources=[ref.label for ref in context.evidence],
            trace=context.execution_trace,
        )

query_service = QueryService()

__all__ = ["QueryService", "query_service"]
