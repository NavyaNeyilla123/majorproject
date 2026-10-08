import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.core.config import settings
from app.core.data_loader import data_loader
from app.models.evaluation import EvaluationQuestion

CITATION_PATTERN = re.compile(r"(?:Issue\s*#\s*\d+|PR\s*#\s*\d+|GM-\d+)", re.IGNORECASE)
KEYWORD_PATTERN = re.compile(r"[a-z0-9#]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "no", "not", "of", "on", "or",
    "remains", "should", "that", "the", "their", "there", "this", "to",
    "what", "when", "with", "yes", "you", "your",
}
ANSWER_KEYWORD_THRESHOLD = 0.5

METRIC_NOTES = {
    "precision": (
        "Macro-average over the run: linked citations that match an expected citation / "
        "all linked citations. Scores 0 when expected citations exist but none were linked."
    ),
    "recall": (
        "Macro-average over the run: expected citations found in linked evidence / "
        "expected citations. Expected citations are normalized to source identifiers "
        "(Issue #n, PR #n, GM-xxx)."
    ),
    "f1Score": "Harmonic mean of the measured precision and recall above.",
    "answerAccuracy": (
        "Share of questions where every expected citation was linked AND at least "
        f"{int(ANSWER_KEYWORD_THRESHOLD * 100)}% of the expected-answer keywords appear in the answer."
    ),
    "evidenceAccuracy": (
        "Supported LLM claims / total LLM claims across the run (claim-level grounding "
        "against retrieved records). Null when no claims were produced."
    ),
    "latencySeconds": "Mean end-to-end wall time per question across the run.",
    "failureRate": "Questions that errored / total questions. Errored questions score 0 on quality metrics.",
    "satisfaction": "N/A — not measured (no user study in this environment).",
}

_LOCK = threading.Lock()
_LAST_RUN: Optional[Dict[str, Any]] = None


def normalize_citations(values: Any) -> Set[str]:
    """Extract normalized source identifiers (e.g. 'ISSUE #142', 'GM-064') from citation text."""
    if not values:
        return set()
    if isinstance(values, (list, tuple)):
        text = " ".join(str(v) for v in values)
    else:
        text = str(values)
    return {match.upper() for match in CITATION_PATTERN.findall(text)}


def answer_keywords(expected_answer: str) -> Set[str]:
    tokens = KEYWORD_PATTERN.findall(expected_answer.lower())
    return {t for t in tokens if len(t) > 1 and t not in STOPWORDS}


def keyword_coverage(expected_answer: str, answer: str) -> float:
    expected = answer_keywords(expected_answer)
    if not expected:
        return 1.0
    answer_lower = (answer or "").lower()
    matched = sum(1 for word in expected if word in answer_lower)
    return round(matched / len(expected), 4)


def _percent(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value * 100, 1)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


class EvaluationService:
    """Runs the annotated evaluation set through the real agent pipeline and
    reports only measured metrics. No values are hardcoded or illustrative."""

    def get_questions(self) -> List[EvaluationQuestion]:
        raw = data_loader.load_json("evaluation/questions.json")
        return [EvaluationQuestion(**item) for item in raw]

    def get_overview(self) -> Dict[str, Any]:
        with _LOCK:
            last_run = dict(_LAST_RUN) if _LAST_RUN else None
        questions = self.get_questions()
        snapshot_date = self._snapshot_date()

        if last_run is None:
            return {
                "status": "no_run",
                "dataset": "KnowledgeOps release-readiness eval set",
                "questionsCount": len(questions),
                "snapshotDate": snapshot_date,
                "executedAt": None,
                "message": "No evaluation run completed",
                "metrics": self._empty_metrics(),
                "metricNotes": dict(METRIC_NOTES),
                "questions": [
                    self._question_payload(item, result=None) for item in questions
                ],
            }

        results_by_id = last_run.get("results", {})
        return {
            "status": "completed",
            "dataset": "KnowledgeOps release-readiness eval set",
            "questionsCount": len(questions),
            "snapshotDate": snapshot_date,
            "executedAt": last_run.get("executedAt"),
            "message": None,
            "metrics": last_run.get("metrics"),
            "metricNotes": dict(METRIC_NOTES),
            "questions": [
                self._question_payload(item, result=results_by_id.get(item.id))
                for item in questions
            ],
        }

    def run_evaluation(self) -> Dict[str, Any]:
        global _LAST_RUN
        from app.agents.orchestrator import AgentOrchestrator, AgentPipelineError

        questions = self.get_questions()
        orchestrator = AgentOrchestrator()
        results: Dict[str, Any] = {}
        executed_at = datetime.now(timezone.utc).isoformat()

        for item in questions:
            started = time.perf_counter()
            try:
                context = orchestrator.run(item.question)
                wall_ms = round((time.perf_counter() - started) * 1000, 3)
                result = self._score_question(item, context, wall_ms)
            except AgentPipelineError as exc:
                wall_ms = round((time.perf_counter() - started) * 1000, 3)
                result = self._error_result(
                    item, f"{exc.failed_stage}: {exc.message}", wall_ms
                )
            except Exception as exc:  # noqa: BLE001 - runner must never fail the request
                wall_ms = round((time.perf_counter() - started) * 1000, 3)
                result = self._error_result(item, f"{type(exc).__name__}: {exc}", wall_ms)
            results[item.id] = result

        metrics = self._aggregate(list(results.values()))

        with _LOCK:
            _LAST_RUN = {
                "executedAt": executed_at,
                "metrics": metrics,
                "results": results,
            }

        return self.get_overview()

    def _score_question(
        self, item: EvaluationQuestion, context: Any, wall_ms: float
    ) -> Dict[str, Any]:
        expected = normalize_citations(item.evidence_citations)

        actual: Set[str] = set()
        for ref in context.evidence:
            normalized = normalize_citations(ref.source_id)
            actual |= normalized if normalized else {ref.source_id.upper()}

        retrieved: Set[str] = set()
        for record in context.retrieved_records:
            normalized = normalize_citations(record.source_id)
            retrieved |= normalized if normalized else {record.source_id.upper()}

        matched = expected & actual
        precision = (len(matched) / len(actual)) if actual else (0.0 if expected else 1.0)
        recall = len(matched) / len(expected) if expected else 1.0
        coverage = (len(expected & retrieved) / len(expected)) if expected else 1.0

        claims: List[Any] = []
        if context.llm_response and context.llm_response.evidence_claims:
            claims = list(context.llm_response.evidence_claims)
        supported_claims = sum(1 for c in claims if c.supported)
        groundedness = (supported_claims / len(claims)) if claims else None

        answer = context.final_answer or ""
        coverage_kw = keyword_coverage(item.expected_answer, answer)
        citation_match = bool(expected) and expected <= actual
        correct = citation_match and coverage_kw >= ANSWER_KEYWORD_THRESHOLD

        return {
            "status": "ok",
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(_f1(precision, recall), 4),
            "citationMatch": citation_match,
            "evidenceCoverage": round(coverage, 4),
            "groundedness": round(groundedness, 4) if groundedness is not None else None,
            "claimsSupported": supported_claims,
            "claimsTotal": len(claims),
            "keywordCoverage": coverage_kw,
            "correct": correct,
            "latencyMs": wall_ms,
            "confidence": context.confidence,
            "evidence": [ref.source_id for ref in context.evidence],
            "expected": sorted(expected),
            "answer": answer,
            "error": None,
        }

    def _error_result(
        self, item: EvaluationQuestion, message: str, wall_ms: float
    ) -> Dict[str, Any]:
        expected = normalize_citations(item.evidence_citations)
        return {
            "status": "error",
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "citationMatch": False,
            "evidenceCoverage": 0.0,
            "groundedness": None,
            "claimsSupported": 0,
            "claimsTotal": 0,
            "keywordCoverage": 0.0,
            "correct": False,
            "latencyMs": wall_ms,
            "confidence": "low",
            "evidence": [],
            "expected": sorted(expected),
            "answer": "",
            "error": message,
        }

    @staticmethod
    def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        total = len(results) or 1
        precision = sum(r["precision"] for r in results) / total
        recall = sum(r["recall"] for r in results) / total

        claims_supported = sum(r["claimsSupported"] for r in results)
        claims_total = sum(r["claimsTotal"] for r in results)
        groundedness = (claims_supported / claims_total) if claims_total else None

        correctness = sum(1 for r in results if r["correct"]) / total
        latency = sum(r["latencyMs"] for r in results) / total / 1000
        failure_rate = sum(1 for r in results if r["status"] == "error") / total

        return {
            "precision": _percent(precision),
            "recall": _percent(recall),
            "f1Score": _percent(_f1(precision, recall)),
            "answerAccuracy": _percent(correctness),
            "evidenceAccuracy": _percent(groundedness),
            "latencySeconds": round(latency, 3),
            "failureRate": _percent(failure_rate),
            "satisfaction": None,
        }

    @staticmethod
    def _empty_metrics() -> Dict[str, Optional[float]]:
        return {
            "precision": None,
            "recall": None,
            "f1Score": None,
            "answerAccuracy": None,
            "evidenceAccuracy": None,
            "latencySeconds": None,
            "failureRate": None,
            "satisfaction": None,
        }

    @staticmethod
    def _question_payload(
        item: EvaluationQuestion, result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "id": item.id,
            "question": item.question,
            "expected_answer": item.expected_answer,
            "evidence_citations": item.evidence_citations,
            "result_label": item.result_label,
            "baseline_rag_correct": item.baseline_rag_correct,
            "knowledgeops_ai_correct": item.knowledgeops_ai_correct,
            "result": result,
        }

    @staticmethod
    def _snapshot_date() -> str:
        try:
            path = settings.DATA_ROOT / "evaluation" / "questions.json"
            if not path.exists():
                path = (
                    Path(__file__).resolve().parent.parent.parent.parent
                    / "data"
                    / "evaluation"
                    / "questions.json"
                )
            mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            return f"{mtime.strftime('%b')} {mtime.day}, {mtime.year}"
        except Exception:  # noqa: BLE001
            return "unknown"


evaluation_service = EvaluationService()
