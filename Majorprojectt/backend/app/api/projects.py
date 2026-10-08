from typing import List
from fastapi import APIRouter, HTTPException
from app.models.project import Project
from app.schemas.project import ProjectDetailResponse
from app.services.project_service import project_service

router = APIRouter()

@router.get("/projects", response_model=List[Project])
def get_projects():
    return project_service.get_projects()

@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project_detail(project_id: str):
    detail = project_service.get_project_by_id(project_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Project with ID '{project_id}' not found.")
    return detail
