from fastapi import APIRouter
from app.schemas.dashboard import DashboardOverview
from app.services.dashboard_service import dashboard_service

router = APIRouter()

@router.get("/dashboard", response_model=DashboardOverview)
def get_dashboard():
    return dashboard_service.get_overview()
