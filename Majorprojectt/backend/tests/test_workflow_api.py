import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient

from app.main import app
from app.agents.models import TraceStage
from app.agents.orchestrator import AgentPipelineError

client = TestClient(app)

CRITICAL_QUESTION = "What could delay the Platform API v2.4 release, and what should we do next?"

EXPECTED_AGENT_STAGES = [
    "Planner Agent",
    "Retrieval Agent",
    "Analysis Agent",
    "LLM Agent",
    "Workflow Agent",
    "Evidence Agent",
]


def run_critical_query():
    response = client.post("/api/query", json={"question": CRITICAL_QUESTION})
    assert response.status_code == 200
    return response.json()


# ------------------------------------------------------- 8. POST /api/query

def test_post_query_returns_agent_response_shape():
    data = run_critical_query()
    for key in (
        "run_id", "question", "project", "answer", "risks", "blockers",
        "decisions", "recommended_actions", "evidence", "trace",
        "target_release", "target_date", "status", "confidence", "sources",
    ):
        assert key in data, f"missing key: {key}"
    assert data["run_id"].startswith("KO-")
    assert data["question"] == CRITICAL_QUESTION
    assert [stage["agent"] for stage in data["trace"]] == EXPECTED_AGENT_STAGES
    assert all(stage["status"] == "completed" for stage in data["trace"])
    assert all(stage["duration_ms"] >= 0 for stage in data["trace"])


def test_post_query_agent_failure_returns_structured_error(monkeypatch):
    from app.api import query as query_api

    failure = AgentPipelineError(
        "KO-FAILED01",
        "Planner Agent",
        "planner exploded",
        [TraceStage(agent="Planner Agent", status="failed", error="planner exploded")],
    )

    def boom(request):
        raise failure

    monkeypatch.setattr(query_api.query_service, "process_query", boom)
    response = client.post("/api/query", json={"question": "anything"})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["run_id"] == "KO-FAILED01"
    assert detail["failed_stage"] == "Planner Agent"
    assert detail["error"] == "planner exploded"
    assert detail["trace"][0]["status"] == "failed"


# -------------------------------------------------- 9. GET /api/workflows

def test_get_workflows_lists_recent_runs():
    data = run_critical_query()
    response = client.get("/api/workflows")
    assert response.status_code == 200
    body = response.json()
    assert "runs" in body and "count" in body
    assert body["count"] >= 1
    run_ids = [run["run_id"] for run in body["runs"]]
    assert data["run_id"] in run_ids
    latest = body["runs"][0]
    assert latest["run_id"] == data["run_id"]  # newest first
    assert latest["status"] == "completed"
    assert [stage["agent"] for stage in latest["stages"]] == EXPECTED_AGENT_STAGES
    assert all(stage["duration_ms"] >= 0 for stage in latest["stages"])


# ------------------------------------------- 10. GET /api/workflows/{run_id}

def test_get_workflow_run_detail():
    data = run_critical_query()
    response = client.get(f"/api/workflows/{data['run_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == data["run_id"]
    assert body["question"] == CRITICAL_QUESTION
    assert body["status"] == "completed"
    assert [stage["agent"] for stage in body["stages"]] == EXPECTED_AGENT_STAGES
    assert body["answer"]
    assert body["risks"]
    assert body["recommended_actions"]
    assert body["evidence"]
    assert body["failed_stage"] is None


def test_get_workflow_run_not_found():
    response = client.get("/api/workflows/KO-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ------------------------------------------------------- 11. End-to-end

def test_end_to_end_platform_api_v24_scenario():
    data = run_critical_query()

    # Planner identifies Platform API
    assert data["project"] == "Platform API"
    assert data["trace"][0]["agent"] == "Planner Agent"
    assert data["trace"][0]["status"] == "completed"

    # Retrieval retrieves Issue #142, PR #284, GM-064
    sources = data["sources"]
    assert any("142" in s for s in sources)
    assert any("284" in s for s in sources)
    assert any("GM-064" in s for s in sources)
    evidence_ids = [e["source_id"] for e in data["evidence"]]
    assert "Issue #142" in evidence_ids
    assert "PR #284" in evidence_ids
    assert "GM-064" in evidence_ids

    # Analysis identifies release risk, auth blocker, security review blocker, mandatory approval
    assert data["status"] == "At risk"
    assert any("Issue #142" in b for b in data["blockers"])
    assert any("Authentication migration" in e["claim"] or "Auth migration" in e["claim"] or "authentication migration" in e["claim"].lower() for e in data["evidence"])
    assert any("PR #284" in b and "Security reviewer" in b for b in data["blockers"])
    assert any("Security approval" in d and "mandatory" in d for d in data["decisions"])
    assert any("security review" in r.lower() for r in data["risks"])

    # Workflow creates the three recommendations
    assert data["recommended_actions"] == [
        "Assign a security reviewer for PR #284",
        "Confirm the remaining release scope",
        "Recheck release readiness after security approval",
    ]
    assert all(a["status"] == "draft" for a in data["action_details"])

    # Final answer communicates at risk, not confirmed delay
    answer = data["answer"].lower()
    assert "currently at risk" in answer
    assert "release-blocking" in answer
    assert "pr #284" in answer
    assert "gm-064" in answer
    assert "will definitely" not in answer
    assert "confirmed delay" not in answer
    assert "will be delayed" not in answer

    # Workflow trace retrievable after the run
    detail = client.get(f"/api/workflows/{data['run_id']}")
    assert detail.status_code == 200
    trace = detail.json()
    assert [s["agent"] for s in trace["stages"]] == EXPECTED_AGENT_STAGES
    assert all(s["status"] == "completed" for s in trace["stages"])
    assert trace["evidence"]

    listing = client.get("/api/workflows").json()
    assert data["run_id"] in [r["run_id"] for r in listing["runs"]]
