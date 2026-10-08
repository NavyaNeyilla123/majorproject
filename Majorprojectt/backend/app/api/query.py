from fastapi import APIRouter, HTTPException
from app.agents.orchestrator import AgentPipelineError
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import query_service

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
def post_query(request: QueryRequest):
    try:
        return query_service.process_query(request)
    except AgentPipelineError as exc:
        # Preserve run_id so the failed run stays inspectable via GET /api/workflows/{run_id}.
        raise HTTPException(
            status_code=500,
            detail={
                "run_id": exc.run_id,
                "failed_stage": exc.failed_stage,
                "error": exc.message,
                "trace": [stage.model_dump() for stage in exc.trace],
            },
        )
