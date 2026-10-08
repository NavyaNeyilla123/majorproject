from typing import Dict, Any
from fastapi import APIRouter
from app.services.evaluation_service import evaluation_service

router = APIRouter()

@router.get("/evaluation", response_model=Dict[str, Any])
def get_evaluation():
    return evaluation_service.get_overview()

@router.post("/evaluation/run", response_model=Dict[str, Any])
def run_evaluation():
    return evaluation_service.run_evaluation()
