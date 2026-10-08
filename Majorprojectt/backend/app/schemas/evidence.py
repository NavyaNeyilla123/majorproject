from typing import List, Optional
from pydantic import BaseModel
from app.models.evidence import EvidenceItem, CrossSourceLink

class EvidenceOverviewResponse(BaseModel):
    total_records: int
    github_records_count: int
    gmail_records_count: int
    cross_source_links_count: int
    email_records_count: int
    decision_records_count: int
    risk_records_count: int
    items: List[EvidenceItem]
    cross_source_links: List[CrossSourceLink]
