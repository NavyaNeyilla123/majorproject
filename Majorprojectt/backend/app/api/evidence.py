from fastapi import APIRouter, HTTPException
from app.models.evidence import EvidenceItem
from app.schemas.evidence import EvidenceOverviewResponse
from app.services.evidence_service import evidence_service

router = APIRouter()

@router.get("/evidence", response_model=EvidenceOverviewResponse)
def get_evidence():
    return evidence_service.get_overview()

@router.get("/evidence/{evidence_id}", response_model=EvidenceItem)
def get_evidence_item(evidence_id: str):
    item = evidence_service.get_evidence_by_id(evidence_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Evidence with ID '{evidence_id}' not found.")
    return item
