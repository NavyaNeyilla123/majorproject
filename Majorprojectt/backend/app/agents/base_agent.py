import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from app.agents.models import AgentContext


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class BaseAgent(ABC):
    """Common lifecycle for every agent: name, run(), status, timings, error handling."""

    name: str = "Base Agent"

    def __init__(self) -> None:
        self.status: str = "pending"
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.started_at: str = ""
        self.ended_at: str = ""
        self.error: Optional[str] = None
        self.detail: str = ""

    @abstractmethod
    def execute(self, context: AgentContext) -> AgentContext:
        """Perform this agent's single responsibility and return the updated context."""

    def run(self, context: AgentContext) -> AgentContext:
        self.status = "running"
        self.error = None
        self.started_at = utc_now_iso()
        self.start_time = time.perf_counter()
        try:
            result = self.execute(context)
            self.status = "completed"
            return result
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc) or exc.__class__.__name__
            raise
        finally:
            self.end_time = time.perf_counter()
            self.duration_ms = round((self.end_time - self.start_time) * 1000, 3)
            self.ended_at = utc_now_iso()
