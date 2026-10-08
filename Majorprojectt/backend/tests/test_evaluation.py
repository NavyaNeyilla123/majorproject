import sys
from pathlib import Path

from fastapi.testclient import TestClient

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import app.services.evaluation_service  # noqa: F401 - ensure module import
from app.main import app

# the package re-exports the `evaluation_service` instance under the same
# attribute name as the submodule, so resolve the module from sys.modules
evaluation_module = sys.modules["app.services.evaluation_service"]

client = TestClient(app)

FIGMA_MARKERS = [
    "Demo release-readiness benchmark",
    "86.9",
    "90.0%",
    "4.8 s",
    "4.5 / 5",
    "Illustrative values",
]


def test_evaluation_no_run_state(monkeypatch):
    monkeypatch.setattr(evaluation_module, "_LAST_RUN", None)
    response = client.get("/api/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_run"
    assert data["message"] == "No evaluation run completed"
    assert data["executedAt"] is None
    assert data["questionsCount"] == 4
    assert "questions" in data
    assert all(q["result"] is None for q in data["questions"])
    for value in data["metrics"].values():
        assert value is None
    body = response.text
    for marker in FIGMA_MARKERS:
        assert marker not in body
    assert "not measured" in data["metricNotes"]["satisfaction"].lower()


def test_evaluation_run_endpoint():
    response = client.post("/api/evaluation/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["executedAt"]
    assert data["message"] is None
    assert data["questionsCount"] == 4

    metrics = data["metrics"]
    for key in (
        "precision",
        "recall",
        "f1Score",
        "answerAccuracy",
        "evidenceAccuracy",
        "latencySeconds",
        "failureRate",
        "satisfaction",
    ):
        assert key in metrics
    for key in (
        "precision",
        "recall",
        "f1Score",
        "answerAccuracy",
        "latencySeconds",
        "failureRate",
    ):
        assert isinstance(metrics[key], (int, float)), f"{key} must be measured"
        assert metrics[key] >= 0
    assert 0 <= metrics["precision"] <= 100
    assert 0 <= metrics["recall"] <= 100
    assert metrics["satisfaction"] is None
    assert "not measured" in data["metricNotes"]["satisfaction"].lower()
    assert "macro-average" in data["metricNotes"]["precision"].lower()

    assert all(q["result"] is not None for q in data["questions"])
    assert all(q["result"]["status"] in ("ok", "error") for q in data["questions"])


def test_evaluation_persists_for_get_after_run():
    run = client.post("/api/evaluation/run").json()
    fetched = client.get("/api/evaluation").json()
    assert fetched["status"] == "completed"
    assert fetched["executedAt"] == run["executedAt"]
    assert fetched["metrics"] == run["metrics"]


def test_evaluation_critical_question_measured_result():
    client.post("/api/evaluation/run")
    data = client.get("/api/evaluation").json()
    q1 = next(q for q in data["questions"] if q["id"] == "eval-q1")
    result = q1["result"]
    assert result["status"] == "ok"
    assert result["error"] is None
    assert {"Issue #142", "PR #284", "GM-064"} <= set(result["evidence"])
    assert result["expected"] == ["GM-064", "ISSUE #142", "PR #284"]
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["evidenceCoverage"] == 1.0
    assert result["groundedness"] is not None
    assert result["correct"] is True
    assert result["latencyMs"] > 0


def test_evaluation_no_fabricated_satisfaction_or_baseline(monkeypatch):
    monkeypatch.setattr(evaluation_module, "_LAST_RUN", None)
    no_run = client.get("/api/evaluation").json()
    assert no_run["metrics"]["satisfaction"] is None
    run = client.post("/api/evaluation/run").json()
    assert run["metrics"]["satisfaction"] is None
    body = client.get("/api/evaluation").text
    for marker in FIGMA_MARKERS:
        assert marker not in body
