from typing import List, Optional
from pydantic import BaseModel, Field

class Thread(BaseModel):
    id: str
    subject: str
    project_id: Optional[str] = ""
    project_name: Optional[str] = ""
    category: str = "Email"
    is_release_blocker: bool = False
    message_count: int = 1
    participants: List[str] = Field(default_factory=list)
    snippet: Optional[str] = ""
    last_message_at: Optional[str] = ""
    created_at: Optional[str] = ""

class Email(BaseModel):
    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: Optional[str] = ""
    recipients: List[str] = Field(default_factory=list)
    project_id: Optional[str] = ""
    project_name: Optional[str] = ""
    received_at: Optional[str] = ""
    body: Optional[str] = ""
    is_priority: bool = False
    category: str = "Email"
