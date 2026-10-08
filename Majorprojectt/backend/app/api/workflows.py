from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.agents.orchestrator import run_store
from app.schemas.workflow import WorkflowListResponse, WorkflowRunDetail, WorkflowRunSummary

router = APIRouter()

@router.get("/workflows", response_model=WorkflowListResponse)
def get_workflows(limit: Optional[int] = Query(default=20, ge=1, le=50)):
    runs = [WorkflowRunSummary.model_validate(snapshot) for snapshot in run_store.list_runs(limit)]
    return WorkflowListResponse(runs=runs, count=len(runs))

@router.get("/workflows/{run_id}", response_model=WorkflowRunDetail)
def get_workflow(run_id: str):
    snapshot = run_store.get(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Workflow run '{run_id}' not found")
    return WorkflowRunDetail.model_validate(snapshot)
