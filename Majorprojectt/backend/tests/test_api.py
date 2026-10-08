import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_dashboard_endpoint():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert data["metrics"]["repositories_count"] == 12
    assert data["metrics"]["open_issues_count"] >= 40

def test_projects_endpoint():
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 5

def test_project_detail_endpoint():
    response = client.get("/api/projects/proj-platform-api")
    assert response.status_code == 200
    detail = response.json()
    assert detail["project"]["name"] == "Platform API"

def test_github_endpoints():
    repos_res = client.get("/api/github/repositories")
    assert repos_res.status_code == 200
    assert len(repos_res.json()) == 12

    issues_res = client.get("/api/github/issues")
    assert issues_res.status_code == 200
    assert len(issues_res.json()) >= 40

    prs_res = client.get("/api/github/pull-requests")
    assert prs_res.status_code == 200
    assert len(prs_res.json()) >= 15

def test_gmail_endpoints():
    emails_res = client.get("/api/gmail/emails")
    assert emails_res.status_code == 200
    assert len(emails_res.json()) >= 10

    threads_res = client.get("/api/gmail/threads")
    assert threads_res.status_code == 200
    assert len(threads_res.json()) >= 20

def test_evidence_endpoint():
    response = client.get("/api/evidence")
    assert response.status_code == 200
    data = response.json()
    assert "cross_source_links" in data

def test_evaluation_endpoint():
    response = client.get("/api/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert "questions" in data

def test_platform_api_v24_scenario_query():
    payload = {
        "question": "What could delay the Platform API v2.4 release, and what should we do next?"
    }
    response = client.post("/api/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["project"] == "Platform API"
    assert data["status"] == "At risk"
    
    # Assert answer facts
    answer = data["answer"]
    assert "release-blocking" in answer.lower() or "blocking" in answer.lower()
    assert "PR #284" in answer or "284" in answer
    assert "GM-064" in answer
    assert "will definitely" not in answer.lower()
    
    # Assert evidence citations include Issue #142, PR #284, GM-064
    sources = data["sources"]
    assert any("142" in s for s in sources)
    assert any("284" in s for s in sources)
    assert any("GM-064" in s for s in sources)
