from typing import List
from pydantic import BaseModel, Field

class EvaluationQuestion(BaseModel):
    id: str
    question: str
    expected_answer: str
    evidence_citations: List[str] = Field(default_factory=list)
    result_label: str
    baseline_rag_correct: bool
    knowledgeops_ai_correct: bool
