from typing import List, Optional
from pydantic import BaseModel, Field

class Project(BaseModel):
    id: str
    name: str
    key: Optional[str] = ""
    code: Optional[str] = ""
    owner: Optional[str] = ""
    engineering_lead: Optional[str] = ""
    release_lead: Optional[str] = ""
    security_lead: Optional[str] = ""
    lead: Optional[str] = ""
    target_release: Optional[str] = ""
    target_date: Optional[str] = ""
    status: Optional[str] = "Healthy"
    health_status: Optional[str] = "Healthy"
    health_score: Optional[int] = 80
    repositories: List[str] = Field(default_factory=list)
    description: Optional[str] = ""
    created_at: Optional[str] = ""
    updated_at: Optional[str] = ""
