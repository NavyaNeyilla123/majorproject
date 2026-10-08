from typing import List, Optional
from pydantic import BaseModel
from app.models.gmail import Thread, Email

class GmailStats(BaseModel):
    relevant_email_count: int
    emails_received_this_week: int
    project_risks_count: int
    priority_threads_count: int

class ExtractedDecision(BaseModel):
    id: str
    decision: str
    source_thread: str
    owner: str
    date: str

class ExtractedRisk(BaseModel):
    id: str
    risk: str
    severity: str
    source_thread: str
    impact: str

class ExtractedAction(BaseModel):
    id: str
    action: str
    owner: str
    due: str
    source_thread: str

class GmailOverviewResponse(BaseModel):
    stats: GmailStats
    threads: List[Thread]
    emails: List[Email]
    extracted_decisions: List[ExtractedDecision]
    extracted_risks: List[ExtractedRisk]
    extracted_actions: List[ExtractedAction]
