from typing import Optional

from fastapi import APIRouter, Body

from app.schemas.report import ReportGenerateResponse
from app.services.report_service import report_service

router = APIRouter()


@router.post("/reports/generate", response_model=ReportGenerateResponse)
def generate_report(
    payload: Optional[dict] = Body(default=None),
) -> ReportGenerateResponse:
    """Generate a release-readiness report from backend repository data.

    Every count, risk, action and citation is derived from the current
    GitHub + Gmail dataset; provenance (agent run, MCP/RAG/LLM mode,
    generation time) comes from live service status.
    """
    project_id = "proj-platform-api"
    if isinstance(payload, dict) and payload.get("project_id"):
        project_id = str(payload["project_id"])
    return report_service.generate(project_id)


@router.get("/reports/latest", response_model=ReportGenerateResponse)
def latest_report(project_id: str = "proj-platform-api") -> ReportGenerateResponse:
    """Most recently generated report for a project (report=None before first run)."""
    return report_service.latest(project_id)
