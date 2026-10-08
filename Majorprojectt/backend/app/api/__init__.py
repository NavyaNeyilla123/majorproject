from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.dashboard import router as dashboard_router
from app.api.projects import router as projects_router
from app.api.github import router as github_router
from app.api.gmail import router as gmail_router
from app.api.evidence import router as evidence_router
from app.api.query import router as query_router
from app.api.workflows import router as workflows_router
from app.api.evaluation import router as evaluation_router
from app.api.mcp import router as mcp_router
from app.api.rag import router as rag_router
from app.api.llm import router as llm_router
from app.api.reports import router as reports_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(dashboard_router, tags=["Dashboard"])
api_router.include_router(projects_router, tags=["Projects"])
api_router.include_router(github_router, tags=["GitHub"])
api_router.include_router(gmail_router, tags=["Gmail"])
api_router.include_router(evidence_router, tags=["Evidence"])
api_router.include_router(query_router, tags=["Query"])
api_router.include_router(workflows_router, tags=["Workflows"])
api_router.include_router(evaluation_router, tags=["Evaluation"])
api_router.include_router(mcp_router, tags=["MCP"])
api_router.include_router(rag_router, tags=["RAG"])
api_router.include_router(llm_router, tags=["LLM"])
api_router.include_router(reports_router, tags=["Reports"])
