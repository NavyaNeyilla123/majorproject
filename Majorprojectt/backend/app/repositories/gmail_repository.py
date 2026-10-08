from typing import List, Optional
from app.core.data_loader import data_loader
from app.models.gmail import Thread, Email

class GmailRepository:
    def get_threads(self) -> List[Thread]:
        raw = data_loader.load_json("gmail/threads.json")
        return [Thread(**item) for item in raw]

    def get_thread_by_id(self, thread_id: str) -> Optional[Thread]:
        for thread in self.get_threads():
            if thread.id == thread_id:
                return thread
        return None

    def get_emails(self) -> List[Email]:
        raw = data_loader.load_json("gmail/emails.json")
        return [Email(**item) for item in raw]

    def get_emails_by_thread_id(self, thread_id: str) -> List[Email]:
        return [email for email in self.get_emails() if email.thread_id == thread_id]

gmail_repository = GmailRepository()
