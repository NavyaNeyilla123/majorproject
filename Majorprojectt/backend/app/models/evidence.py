from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class PrimaryBlockerIssue(BaseModel):
    id: Optional[int] = None
    number: Optional[int] = None
    title: Optional[str] = ""
    repository: Optional[str] = ""
    status: Optional[str] = "open"
    is_release_blocker: bool = True

class PrimaryBlockerPR(BaseModel):
    id: Optional[int] = None
    number: Optional[int] = None
    title: Optional[str] = ""
    repository: Optional[str] = ""
    status: Optional[str] = "open"
    ci_status: Optional[str] = "passed"
    security_reviewer_assigned: bool = False

class PrimaryBlockerThread(BaseModel):
    id: Optional[str] = ""
    subject: Optional[str] = ""
    category: Optional[str] = "Risk"
    messages_count: Optional[int] = 1
    last_message_at: Optional[str] = ""

class PrimaryBlocker(BaseModel):
    github_issue: Optional[PrimaryBlockerIssue] = None
    github_pr: Optional[PrimaryBlockerPR] = None
    gmail_thread: Optional[PrimaryBlockerThread] = None

class CrossSourceLink(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = ""
    target_release: Optional[str] = ""
    target_date: Optional[str] = ""
    description: Optional[str] = ""
    primary_blocker: Optional[PrimaryBlocker] = None
    provenance_facts: List[str] = Field(default_factory=list)
    linked_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_trail: List[Dict[str, Any]] = Field(default_factory=list)
    github_pr: Optional[Dict[str, Any]] = None
    gmail_thread: Optional[Dict[str, Any]] = None
    status: Optional[str] = ""

class EvidenceLinkedIntel(BaseModel):
    title: str = ""
    sources: str = ""
    context: str = ""

class EvidenceDetail(BaseModel):
    title: str = ""
    thread: str = ""
    author: str = ""
    received_display: str = ""
    project: str = ""
    source_access: str = ""
    excerpt_label: str = ""
    excerpt: str = ""
    claims: List[str] = Field(default_factory=list)
    context_note: str = ""
    linked_intel: EvidenceLinkedIntel = Field(default_factory=EvidenceLinkedIntel)
    metadata: Dict[str, str] = Field(default_factory=dict)
    open_label: str = ""

class EvidenceItem(BaseModel):
    id: str
    title: str
    source_type: str
    source_ref: str
    project_id: str
    project_name: str
    relevance_score: float
    excerpt: str
    author_sender: str
    timestamp: str
    url_route: str
    kind: str = ""
    kind_color: str = "gray"
    subtitle: str = ""
    source_line: str = ""
    badges: List[Dict[str, str]] = Field(default_factory=list)
    detail: Optional[EvidenceDetail] = None
