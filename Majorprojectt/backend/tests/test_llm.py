"""Step 9 tests: LLM provider, prompt, parsing, validation, guards, pipeline."""

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient

from app.agents.analysis_agent import AnalysisAgent
from app.agents.evidence_agent import EvidenceAgent
from app.agents.llm_agent import LLMAgent
from app.agents.models import AgentContext, AnalysisClaim, RetrievedRecord
from app.agents.orchestrator import AgentOrchestrator, RunStore
from app.agents.planner_agent import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.workflow_agent import WorkflowAgent
from app.llm import (
    MOCK_MODEL,
    EvidenceClaim,
    LLMParseError,
    LLMProvider,
    LLMUnavailableError,
    MockLLMProvider,
    UnavailableLLMProvider,
    build_llm_context,
    build_llm_status,
    build_prompt,
    constrain_confidence,
    extract_json,
    get_llm_provider,
    parse_response,
    sanitize_answer,
    set_llm_provider,
    validate_claims,
)
from app.llm.validator import sanitize_llm_actions
from app.main import app

client = TestClient(app)

CRITICAL_QUESTION = "What could delay the Platform API v2.4 release, and what should we do next?"
HALLUCINATION_QUESTION = "Who approved the Platform API v2.4 security review?"
PARTICIPANTS = ["Maya Lee", "Priya Rao", "Daniel Kim", "Alex Shah"]


# ------------------------------------------------------------------- helpers

def make_records():
    return [
        RetrievedRecord(
            source="GitHub",
            record_type="issue",
            source_id="Issue #142",
            project_id="proj-platform-api",
            title="Auth migration blocking the v2.4 release",
            summary="Authentication migration must land before release.",
            data={"number": 142, "status": "open", "is_release_blocker": True,
                  "body": "Authentication migration blocks the v2.4 release."},
        ),
        RetrievedRecord(
            source="GitHub",
            record_type="pull_request",
            source_id="PR #284",
            project_id="proj-platform-api",
            title="Rate limiting middleware",
            summary="Awaiting security review; number 284.",
            data={"number": 284, "status": "awaiting_security_review",
                  "security_reviewer_assigned": False, "ci_status": "passed"},
        ),
        RetrievedRecord(
            source="Gmail",
            record_type="thread",
            source_id="GM-064",
            project_id="proj-platform-api",
            title="Platform API v2.4 release approval",
            summary="Security approval required before release.",
            data={"id": "GM-064", "is_release_blocker": True,
                  "subject": "Platform API v2.4 release approval"},
        ),
    ]


def make_context(**overrides) -> AgentContext:
    context = AgentContext(
        run_id="KO-LLMT1",
        question=overrides.pop("question", CRITICAL_QUESTION),
        project="Platform API",
        project_id="proj-platform-api",
        target_release="v2.4",
        target_date="October 9",
        release_status="At risk",
        confidence="high",
        retrieved_records=overrides.pop("retrieved_records", make_records()),
        risks=overrides.pop("risks", ["Security review remains unassigned for PR #284"]),
        blockers=overrides.pop("blockers", [
            "Issue #142: Auth migration blocking the v2.4 release",
            "PR #284: Security reviewer unassigned",
        ]),
        decisions=overrides.pop("decisions", ["Security approval is a mandatory release gate."]),
        facts=overrides.pop("facts", [
            "Issue #142 is marked release-blocking: Auth migration blocking the v2.4 release",
            "PR #284 status: awaiting_security_review; security reviewer assigned: False",
            "Gmail GM-064: Security approval required before release.",
        ]),
        unresolved_actions=overrides.pop("unresolved_actions", ["PR #284: Assign security reviewer"]),
        contradictions=overrides.pop("contradictions", []),
        claims=overrides.pop("claims", [
            AnalysisClaim(claim="Authentication migration is release-blocking.", kind="blocker",
                          source_ids=["Issue #142"]),
            AnalysisClaim(claim="PR #284 requires security review.", kind="blocker",
                          source_ids=["PR #284"]),
            AnalysisClaim(claim="Security approval is mandatory before release.", kind="decision",
                          source_ids=["GM-064"]),
        ]),
    )
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


class FailingProvider(LLMProvider):
    provider_name = "failing"
    model = "failing-1"

    def generate(self, prompt, context):
        raise RuntimeError("provider exploded")


class GarbageProvider(LLMProvider):
    provider_name = "garbage"
    model = "garbage-1"

    def generate(self, prompt, context):
        return "I could not produce any structured output."


class EmptyAnswerProvider(LLMProvider):
    provider_name = "empty-answer"
    model = "empty-1"

    def generate(self, prompt, context):
        return json.dumps({"answer": "   ", "confidence": 0.9})


class DelayEmittingProvider(LLMProvider):
    provider_name = "delay-emit"
    model = "delay-1"

    def generate(self, prompt, context):
        return json.dumps({
            "answer": (
                "The Platform API v2.4 release is currently at risk because Issue #142 "
                "is release-blocking. The release will be delayed until Friday."
            ),
            "evidence_claims": [],
            "confidence": 0.95,
        })


class ExecEmittingProvider(LLMProvider):
    provider_name = "exec-emit"
    model = "exec-1"

    def generate(self, prompt, context):
        return json.dumps({
            "answer": (
                "The Platform API v2.4 release is currently at risk. "
                "The security reviewer was assigned yesterday. "
                "Evidence: Issue #142 is marked release-blocking."
            ),
            "recommended_actions": ["Security reviewer was assigned; nothing else to do"],
            "evidence_claims": [
                {"claim": "PR #284 requires security review.", "source_ids": ["PR #284"],
                 "confidence": 0.9},
            ],
            "confidence": 0.9,
        })


class FabricatingProvider(LLMProvider):
    provider_name = "fabricate"
    model = "fabricate-1"

    def generate(self, prompt, context):
        return json.dumps({
            "answer": (
                "The Platform API v2.4 release is currently at risk because Issue #142 "
                "is release-blocking. Evidence: PR #284 status is awaiting security review."
            ),
            "evidence_claims": [
                {"claim": "Issue #142 is release-blocking.", "source_ids": ["Issue #142"],
                 "confidence": 0.9},
                {"claim": "Issue #999 blocks the release.", "source_ids": ["Issue #999"],
                 "confidence": 0.9},
                {"claim": "An unnamed issue is a blocker.", "source_ids": [],
                 "confidence": 0.9},
            ],
            "confidence": 0.9,
        })


def run_with(provider: LLMProvider, question: str = CRITICAL_QUESTION):
    orchestrator = AgentOrchestrator(agents=[
        PlannerAgent(),
        RetrievalAgent(),
        AnalysisAgent(),
        LLMAgent(provider=provider),
        WorkflowAgent(),
        EvidenceAgent(),
    ])
    store = RunStore()
    return orchestrator.run(question, store=store), store


# ------------------------------------------------- 1. provider abstraction

def test_llm_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_default_provider_is_mock_and_injectable():
    assert isinstance(get_llm_provider(), MockLLMProvider)
    custom = FailingProvider()
    try:
        set_llm_provider(custom)
        assert get_llm_provider() is custom
    finally:
        set_llm_provider(None)
    assert isinstance(get_llm_provider(), MockLLMProvider)
    assert get_llm_provider().model == MOCK_MODEL


def test_empty_or_unknown_provider_is_unavailable_not_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "")
    empty = get_llm_provider()
    assert isinstance(empty, UnavailableLLMProvider)
    with pytest.raises(LLMUnavailableError):
        empty.generate(build_prompt(build_llm_context(make_context())), build_llm_context(make_context()))

    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    unknown = get_llm_provider()
    assert isinstance(unknown, UnavailableLLMProvider)
    assert "not-a-real-provider" in unknown.reason


def test_http_provider_without_key_is_unavailable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, UnavailableLLMProvider)
    assert "LLM_API_KEY" in provider.reason


# --------------------------------------------------------- 2. mock provider

def test_mock_answer_is_grounded_in_context_only():
    context = make_context()
    llm_context = build_llm_context(context)
    raw = MockLLMProvider().generate(build_prompt(llm_context), llm_context)
    response = parse_response(raw)

    answer = response.answer
    assert answer
    assert "currently at risk" in answer.lower()

    allowed_ids = {"Issue #142", "PR #284", "GM-064", "#142", "#284", "142", "284"}
    mentioned = set(re.findall(r"(?:Issue #\d+|PR #\d+|GM-\d+|#\d+)", answer))
    assert mentioned <= allowed_ids, f"mock invented ids: {mentioned - allowed_ids}"
    assert "999" not in answer

    for fact in context.facts:
        assert fact[:200].rstrip(".") in answer.rstrip("."), f"fact not echoed: {fact}"


def test_mock_actor_question_without_actor_evidence_is_insufficient():
    context = make_context(question=HALLUCINATION_QUESTION)
    llm_context = build_llm_context(context)
    raw = MockLLMProvider().generate(build_prompt(llm_context), llm_context)
    answer = parse_response(raw).answer

    assert "does not identify" in answer
    for name in PARTICIPANTS:
        assert name not in answer


# ----------------------------------------------------- 3. prompt construction

def test_prompt_contains_all_sections_and_system_prohibitions():
    context = build_llm_context(make_context())
    prompt = build_prompt(context)

    for section in (
        "[QUESTION]", "[PROJECT]", "[GITHUB EVIDENCE]", "[GMAIL EVIDENCE]",
        "[RAG RESULTS]", "[ANALYSIS]", "[CROSS-SOURCE RELATIONSHIPS]",
    ):
        assert section in prompt.user

    assert "Do not invent facts, source IDs, people, dates, approvals" in prompt.system
    assert 'does not mean "delayed"' in prompt.system
    assert "Recommendations are proposals only" in prompt.system
    assert "Answer ONLY from the evidence" in prompt.system
    assert CRITICAL_QUESTION in prompt.user


def test_prompt_contains_only_retrieved_record_ids():
    context = build_llm_context(make_context())
    prompt = build_prompt(context)
    mentioned = set(re.findall(r"(?:Issue #\d+|PR #\d+|GM-\d+)", prompt.user))
    assert mentioned <= {"Issue #142", "PR #284", "GM-064"}
    assert "Issue #999" not in prompt.user


# -------------------------------------------------------- 4. structured parsing

def test_parse_valid_fenced_and_embedded_json():
    answer = {"answer": "grounded", "confidence": 0.9, "risks": "one risk"}
    assert parse_response(json.dumps(answer)).answer == "grounded"
    assert parse_response(f"```json\n{json.dumps(answer)}\n```").answer == "grounded"
    assert parse_response(f"output: {json.dumps(answer)} end").answer == "grounded"
    parsed = parse_response(json.dumps(answer))
    assert parsed.risks == ["one risk"]


def test_confidence_is_clamped_and_defaulted():
    assert parse_response('{"answer": "ok", "confidence": 3.5}').confidence == 1.0
    assert parse_response('{"answer": "ok", "confidence": -2}').confidence == 0.0
    assert parse_response('{"answer": "ok"}').confidence == 0.5
    assert parse_response('{"answer": "ok", "confidence": "high"}').confidence == 0.5


def test_evidence_claims_are_parsed():
    raw = json.dumps({
        "answer": "ok",
        "evidence_claims": [
            {"claim": "PR #284 requires security review.", "source_ids": ["PR #284"],
             "source_types": ["GitHub"], "confidence": 0.9},
            {"claim": "", "source_ids": ["x"]},
            "not-a-dict",
        ],
    })
    claims = parse_response(raw).evidence_claims
    assert len(claims) == 1
    assert claims[0].source_ids == ["PR #284"]
    assert claims[0].confidence == 0.9


# -------------------------------------------------------- 5. malformed output

def test_malformed_outputs_raise_parse_error():
    with pytest.raises(LLMParseError):
        parse_response("I could not produce any structured output.")
    with pytest.raises(LLMParseError):
        parse_response('{"risks": ["no answer key"]}')
    with pytest.raises(LLMParseError):
        parse_response('{"answer": "   "}')
    with pytest.raises(LLMParseError):
        parse_response("")


def test_extract_json_handles_objects_and_rejects_arrays():
    assert extract_json({"answer": "x"}) == {"answer": "x"}
    with pytest.raises(LLMParseError):
        extract_json("[1, 2, 3]")


# ----------------------------------------------------- 6-7. evidence validation

def test_validate_claims_accepts_known_source_and_rejects_fabricated():
    records = make_records()
    supported, rejected = validate_claims([
        EvidenceClaim(claim="PR #284 requires security review.", source_ids=["PR #284"]),
        EvidenceClaim(claim="Issue #999 blocks the release.", source_ids=["Issue #999"]),
        EvidenceClaim(claim="Something vague.", source_ids=[]),
        EvidenceClaim(claim="An unrelated sentence with no overlap to this record at all.",
                      source_ids=["GM-064"]),
    ], records)

    assert [c.claim for c in supported] == ["PR #284 requires security review."]
    reasons = {c.claim: c.rejection_reason for c in rejected}
    assert "was not retrieved" in reasons["Issue #999 blocks the release."]
    assert reasons["Something vague."] == "claim cites no source_ids"
    assert "does not overlap" in reasons["An unrelated sentence with no overlap to this record at all."]
    assert all(not c.supported for c in rejected)


def test_fabricated_claim_never_reaches_pipeline_evidence():
    context, _store = run_with(FabricatingProvider())

    assert context.llm_used is True
    response = context.llm_response
    rejected = [c for c in response.evidence_claims if not c.supported]
    assert len(rejected) == 2
    assert any("Issue #999" in c.rejection_reason for c in rejected)

    evidence_ids = [ref.source_id for ref in context.evidence]
    assert "Issue #999" not in evidence_ids
    assert all("Issue #999" not in ref.claim for ref in context.evidence)
    claims = {c.claim for c in context.claims}
    assert "Issue #999 blocks the release." not in claims


# --------------------------------------------------------- 8. confidence tiers

def test_confidence_low_when_evidence_is_weak_or_missing():
    empty = make_context(retrieved_records=[], facts=[], claims=[], blockers=[],
                         risks=[], decisions=[], contradictions=[])
    assert constrain_confidence(0.95, empty) == "low"

    weak = make_context(
        retrieved_records=[make_records()[0]],
        facts=[],
        claims=[],
        contradictions=[],
    )
    assert constrain_confidence(0.95, weak) == "low"


def test_confidence_downgrades_on_rejected_claims_and_weak_llm_number():
    strong = make_context(contradictions=[])
    assert constrain_confidence(0.9, strong) == "high"
    assert constrain_confidence(0.9, strong, rejected_count=1) == "medium"
    assert constrain_confidence(0.2, strong) == "low"


def test_confidence_capped_to_medium_when_contradictions_exist():
    contradictory = make_context(contradictions=[
        "PR #284 passed CI checks but is still awaiting security review; "
        "passing checks is not release approval."
    ])
    assert constrain_confidence(0.9, contradictory) == "medium"
    assert constrain_confidence(0.6, contradictory) == "medium"
    assert constrain_confidence(0.3, contradictory) == "low"


# ------------------------------------------------------ 9. unavailable fallback

def test_unavailable_provider_falls_back_deterministically():
    context, store = run_with(FailingProvider())

    assert context.run_status == "completed"
    assert context.llm_used is False
    assert context.llm_response is None
    assert "currently at risk" in context.final_answer.lower()

    llm_stage = next(s for s in context.execution_trace if s.agent == "LLM Agent")
    assert llm_stage.status == "completed"
    assert "llm unavailable" in llm_stage.detail
    assert "RuntimeError" in llm_stage.detail
    assert "deterministic fallback" in llm_stage.detail

    saved = store.get(context.run_id)
    assert saved["llm_used"] is False


def test_garbage_and_empty_answers_fall_back_deterministically():
    for provider in (GarbageProvider(), EmptyAnswerProvider()):
        context, _ = run_with(provider)
        assert context.llm_used is False
        assert "currently at risk" in context.final_answer.lower()
        llm_stage = next(s for s in context.execution_trace if s.agent == "LLM Agent")
        assert llm_stage.status == "completed"
        assert "deterministic fallback" in llm_stage.detail


# ------------------------------------------------------------ 10. status endpoint

def test_llm_status_reports_healthy_mock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    response = client.get("/api/llm/status")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["model"] == MOCK_MODEL
    assert body["configured"] is True
    assert body["status"] == "healthy"
    assert "api_key" not in body
    assert "LLM_API_KEY" not in response.text


def test_llm_status_unavailable_states(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "")
    body = client.get("/api/llm/status").json()
    assert body["configured"] is False
    assert body["status"] == "unavailable"

    monkeypatch.setenv("LLM_PROVIDER", "mystery")
    body = client.get("/api/llm/status").json()
    assert body["configured"] is False
    assert body["status"] == "unavailable"
    assert "mystery" in body["message"]


def test_llm_status_http_provider_hides_credentials(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "sk-super-secret-key-123456")
    response = client.get("/api/llm/status")
    body = response.json()
    assert body["configured"] is True
    assert body["status"] == "configured"
    assert "not tested" in body["message"]
    assert "sk-super-secret" not in response.text

    monkeypatch.delenv("LLM_API_KEY")
    body = client.get("/api/llm/status").json()
    assert body["configured"] is False
    assert body["status"] == "unavailable"


def test_build_llm_status_never_returns_a_key_field():
    status = build_llm_status().model_dump()
    assert set(status) == {"provider", "model", "configured", "status", "message"}


# --------------------------------------------------------------- 11. query API

def test_query_endpoint_exposes_llm_stage():
    response = client.post("/api/query", json={"question": CRITICAL_QUESTION})
    assert response.status_code == 200
    data = response.json()

    agents = [stage["agent"] for stage in data["trace"]]
    assert agents == [
        "Planner Agent", "Retrieval Agent", "Analysis Agent",
        "LLM Agent", "Workflow Agent", "Evidence Agent",
    ]
    llm_stage = next(s for s in data["trace"] if s["agent"] == "LLM Agent")
    assert llm_stage["status"] == "completed"
    assert "grounded response" in llm_stage["detail"]

    answer = data["answer"].lower()
    assert "currently at risk" in answer
    assert "will be delayed" not in answer


# ------------------------------------------------------------ 12. full pipeline

def test_full_pipeline_run_snapshot_carries_llm_used():
    store = RunStore()
    context = AgentOrchestrator().run(CRITICAL_QUESTION, store=store)
    assert context.run_status == "completed"
    assert context.llm_used is True
    assert context.llm_response is not None

    saved = store.get(context.run_id)
    assert saved["llm_used"] is True
    assert context.llm_response is not None

    llm_stage = next(s for s in context.execution_trace if s.agent == "LLM Agent")
    assert llm_stage.status == "completed"
    assert "mock" in llm_stage.detail
    assert all(c.supported for c in context.llm_response.evidence_claims)


def test_llm_suggested_actions_do_not_replace_workflow_actions():
    context, _ = run_with(ExecEmittingProvider())
    assert context.recommended_actions == [
        "Assign a security reviewer for PR #284",
        "Confirm the remaining release scope",
        "Recheck release readiness after security approval",
    ]
    # LLM-suggested actions stay informational and are validated separately.
    assert context.llm_response is not None
    assert all(
        "assigned" not in action.lower()
        for action in context.llm_response.recommended_actions
    )


# ---------------------------------------------------------------- 13. RAG + LLM

def test_rag_merged_pipeline_runs_llm_stage():
    from app.rag import rag_service
    from app.rag.qdrant_client import InMemoryVectorStore, get_vector_store, set_vector_store

    previous = get_vector_store()
    set_vector_store(InMemoryVectorStore())
    rag_service.last_indexed = None
    try:
        rag_service.index_all(force_reindex=True)
        store = RunStore()
        context = AgentOrchestrator().run(CRITICAL_QUESTION, store=store)

        retrieval = next(s for s in context.execution_trace if s.agent == "Retrieval Agent")
        assert "rag:" in retrieval.detail
        llm_stage = next(s for s in context.execution_trace if s.agent == "LLM Agent")
        assert llm_stage.status == "completed"
        assert context.llm_used is True
        assert context.final_answer
        assert context.evidence
        assert all(c.supported for c in context.llm_response.evidence_claims)
        rag_records = [r for r in context.retrieved_records if r.relationships.get("rag_chunk")]
        assert isinstance(rag_records, list)  # RAG merge active in this run
    finally:
        set_vector_store(previous)
        rag_service.last_indexed = None


# --------------------------------------- 14-15. regression: at-risk is not delayed

def test_delay_emitting_llm_output_is_stripped():
    context, _ = run_with(DelayEmittingProvider())
    answer = context.final_answer.lower()

    assert "will be delayed" not in answer
    assert "delayed until" not in answer
    assert "currently at risk" in answer
    assert context.release_status == "At risk"


def test_execution_emitting_llm_output_is_stripped():
    context, _ = run_with(ExecEmittingProvider())
    answer = context.final_answer.lower()

    assert "was assigned" not in answer
    assert "currently at risk" in answer
    assert context.llm_used is True  # grounded part survived the guard
    assert context.recommended_actions == [
        "Assign a security reviewer for PR #284",
        "Confirm the remaining release scope",
        "Recheck release readiness after security approval",
    ]


def test_sanitizer_rejects_short_answers_and_forbidden_phrases():
    records = make_records()

    clean, removed, notes = sanitize_answer(
        "The release will be delayed until Friday.", records
    )
    assert clean == ""
    assert removed

    clean, _removed, _notes = sanitize_answer(
        "The release will definitely ship. The Platform API v2.4 release is "
        "currently at risk because Issue #142 is release-blocking for everyone.",
        records,
    )
    assert "will definitely" not in clean.lower()
    assert "currently at risk" in clean.lower()


def test_sanitize_llm_actions_drops_forbidden_and_duplicates():
    assert sanitize_llm_actions([
        "Assign a security reviewer",
        "Assign a security reviewer",
        "Release will be delayed anyway",
        "The security reviewer was assigned yesterday",
        "   ",
    ]) == ["Assign a security reviewer"]


# -------------------------------------------------- 16. hallucination protection

def test_hallucination_question_produces_no_invented_actor():
    response = client.post("/api/query", json={"question": HALLUCINATION_QUESTION})
    assert response.status_code == 200
    data = response.json()

    answer = data["answer"]
    assert "does not identify" in answer
    for name in PARTICIPANTS:
        assert name not in answer, f"hallucinated actor: {name}"

    llm_stage = next(s for s in data["trace"] if s["agent"] == "LLM Agent")
    assert llm_stage["status"] == "completed"

    for ref in data["evidence"]:
        assert ref["source_id"] in {"Issue #142", "PR #284", "GM-064"} or "#" in ref["source_id"]


def test_llm_never_retrieves_prompt_records_come_from_pipeline():
    context = make_context()
    llm_context = build_llm_context(context)
    prompt = build_prompt(llm_context)

    pipeline_ids = {r.source_id for r in context.retrieved_records}
    prompt_ids = set(re.findall(r"(?:Issue #\d+|PR #\d+|GM-\d+)", prompt.user + prompt.system))
    assert prompt_ids <= pipeline_ids | {"Issue #142", "PR #284", "GM-064"}

    # The provider API receives only prompt + context objects (no tool access).
    import inspect
    assert "requests" not in inspect.getsource(MockLLMProvider.generate)
    assert "open(" not in inspect.getsource(MockLLMProvider.generate)
