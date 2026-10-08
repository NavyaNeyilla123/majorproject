from app.services.dashboard_service import DashboardService, dashboard_service
from app.services.github_service import GitHubService, github_service
from app.services.gmail_service import GmailService, gmail_service
from app.services.project_service import ProjectService, project_service
from app.services.evidence_service import EvidenceService, evidence_service
from app.services.evaluation_service import EvaluationService, evaluation_service
from app.services.query_service import QueryService, query_service

__all__ = [
    "DashboardService", "dashboard_service",
    "GitHubService", "github_service",
    "GmailService", "gmail_service",
    "ProjectService", "project_service",
    "EvidenceService", "evidence_service",
    "EvaluationService", "evaluation_service",
    "QueryService", "query_service"
]
