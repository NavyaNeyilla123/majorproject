import sys
from pathlib import Path

from fastapi.testclient import TestClient

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app

client = TestClient(app)

DATASET_PEOPLE = [
    "Alex Shah",
    "Daniel Kim",
    "David Miller",
    "Elena Rostova",
    "Marcus Vance",
    "Maya Lee",
    "Priya Rao",
    "Ravi Kumar",
    "Sarah Chen",
]


def test_empty_question_is_graceful():
    response = client.post("/api/query", json={"question": ""})
    assert response.status_code == 200
    assert "Traceback" not in response.text
    data = response.json()
    assert isinstance(data.get("answer"), str)
    assert data["answer"]


def test_whitespace_question_is_graceful():
    response = client.post("/api/query", json={"question": "   "})
    assert response.status_code == 200
    assert "Traceback" not in response.text
    data = response.json()
    assert isinstance(data.get("answer"), str)
    assert data["answer"]


def test_unknown_project_is_graceful():
    response = client.post(
        "/api/query",
        json={"question": "Tell me about the Quantum Blockchain project shutdown"},
    )
    assert response.status_code == 200
    assert "Traceback" not in response.text
    data = response.json()
    answer = data.get("answer", "")
    assert answer
    # the pipeline must not invent records for a project that does not exist
    assert "Quantum" not in answer
    assert "Blockchain" not in answer


def test_hallucination_question_names_no_approver():
    response = client.post(
        "/api/query",
        json={"question": "Who approved the Platform API v2.4 security review?"},
    )
    assert response.status_code == 200
    assert "Traceback" not in response.text
    data = response.json()
    answer = data["answer"]
    lowered = answer.lower()

    # the honest answer states that no source identifies an approver
    assert any(
        marker in lowered
        for marker in (
            "does not identify",
            "no source names",
            "not identified",
            "does not name",
        )
    ), answer

    # no dataset person may be presented as the approver
    for name in DATASET_PEOPLE:
        assert f"{name.lower()} approved" not in lowered, answer
        assert f"approved by {name.lower()}" not in lowered, answer
        assert name.lower() not in lowered, answer


def test_no_stack_trace_or_secrets_in_query_failures():
    for payload in (
        {"question": ""},
        {"question": "Who approved the Platform API v2.4 security review?"},
        {"question": "x" * 5000},
    ):
        response = client.post("/api/query", json=payload)
        assert response.status_code == 200
        text = response.text
        assert "Traceback" not in text
        assert "api_key" not in text.lower()
        assert "secret" not in text.lower()
        assert "password" not in text.lower()
