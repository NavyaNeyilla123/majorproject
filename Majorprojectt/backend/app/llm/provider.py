"""LLM provider selection (Step 9).

LLM_PROVIDER env var decides which implementation generates answers:

- ``mock`` (default): MockLLMProvider - deterministic, grounded, no network.
- ``openai-compatible`` (aliases: ``openai``, ``http``): OpenAI-compatible HTTP
  chat completions API; requires LLM_API_KEY (and usually LLM_BASE_URL).
- empty / unknown -> an unavailable provider whose generate() raises
  LLMUnavailableError, so the LLM Agent stage falls back deterministically.

Resolution is lazy (at call time, like the MCP seam), so tests can switch
providers through the environment without restarting the process.
"""

import json
import os
import re
from typing import Dict, List, Optional

from app.llm.base import LLMProvider
from app.llm.models import (
    LLMContext,
    LLMPrompt,
    LLMStatus,
    LLMUnavailableError,
)

DEFAULT_LLM_PROVIDER = "mock"
MOCK_MODEL = "mock-grounded-v1"
HTTP_PROVIDER_NAMES = ("openai-compatible", "openai", "http")
DEFAULT_HTTP_MODEL = "gpt-4o-mini"
DEFAULT_HTTP_BASE_URL = "https://api.openai.com/v1"

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|Bearer\s+\S+|api[_-]?key\s*[=:]\s*\S+)", re.IGNORECASE
)


def sanitize_error(message: str) -> str:
    """Strip credential-like tokens from an error message before it goes anywhere."""
    cleaned = _SECRET_RE.sub("[redacted]", str(message))
    return cleaned[:300]


def resolve_llm_provider_name() -> str:
    # Read at call time (unset -> mock; explicitly empty -> unavailable).
    return os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()


class UnavailableLLMProvider(LLMProvider):
    """Placeholder for a provider that cannot serve requests right now."""

    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason
        self.provider_name = "unavailable"
        self.model = ""

    def generate(self, prompt: LLMPrompt, context: LLMContext) -> str:
        raise LLMUnavailableError(self.reason)


class MockLLMProvider(LLMProvider):
    """Deterministic grounded provider (mandatory in this environment).

    Composes the answer strictly from the supplied LLMContext - analysis
    facts, blockers, decisions and unresolved actions are re-emitted, never
    invented. Actor questions ("who...") with no explicit actor evidence in
    the records get an honest insufficiency answer.
    """

    provider_name = "mock"
    model = MOCK_MODEL

    _FORBIDDEN = ("will definitely", "confirmed delay", "will be delayed")
    _ACTOR_RE = re.compile(r"\b(who|whom|whose)\b", re.IGNORECASE)
    _ACTOR_EVIDENCE_RE = re.compile(
        r"\b(?:approved|signed[\- ]off|merged|assigned)\s+by\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
        r"|\bapprover\s*[:=]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
    )

    def generate(self, prompt: LLMPrompt, context: LLMContext) -> str:
        return json.dumps(self._compose(context), indent=2)

    # ------------------------------------------------------------- composition

    def _compose(self, context: LLMContext) -> dict:
        analysis = context.analysis
        confidence = self._confidence(context)
        claims = [
            {
                "claim": claim.claim,
                "source_ids": list(claim.source_ids),
                "source_types": [],
                "confidence": round(confidence, 2),
            }
            for claim in analysis.claims
            if claim.claim.strip()
        ]
        return {
            "answer": self._answer(context),
            "risks": self._safe(analysis.risks),
            "blockers": self._safe(analysis.blockers),
            "decisions": self._safe(analysis.decisions),
            "recommended_actions": self._safe(analysis.unresolved_actions),
            "evidence_claims": claims,
            "confidence": confidence,
        }

    def _safe(self, items) -> List[str]:
        """Echo only items free of forbidden claim phrases (grounding guard)."""
        out: List[str] = []
        for item in items:
            lowered = str(item).lower()
            if any(phrase in lowered for phrase in self._FORBIDDEN):
                continue
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
        return out

    @staticmethod
    def _sentence(text: str) -> str:
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            return ""
        if text[-1] not in ".!?":
            text += "."
        return text

    def _confidence(self, context: LLMContext) -> float:
        records = len(context.github_records) + len(context.gmail_records)
        if not records or not context.analysis.facts:
            return 0.3
        if context.analysis.release_status == "At risk":
            return 0.85
        return 0.7

    def _answer(self, context: LLMContext) -> str:
        question = context.question or ""
        if self._ACTOR_RE.search(question):
            return self._actor_answer(context)

        analysis = context.analysis
        project = context.project or "project"
        release = f" {context.target_release}" if context.target_release else ""

        sentences: List[str] = []

        status = analysis.release_status
        if status == "At risk":
            sentences.append(self._sentence(f"The {project}{release} release is currently at risk"))
            sentences.append("The evidence does not establish an actual delay.")
        elif status and status != "Unknown":
            sentences.append(
                self._sentence(f"The {project}{release} release status in the retrieved records: {status}")
            )

        if analysis.blockers:
            sentences.append(self._sentence("Blocking evidence: " + "; ".join(analysis.blockers)))

        facts = [self._sentence(fact[:200]) for fact in analysis.facts]
        facts = [fact for fact in facts if fact]
        if facts:
            sentences.append("Evidence: " + " ".join(facts))

        if analysis.decisions:
            sentences.append(self._sentence("Decisions in the evidence: " + "; ".join(analysis.decisions)))

        if analysis.unresolved_actions:
            sentences.append(
                self._sentence("Next steps from the evidence: " + "; ".join(analysis.unresolved_actions))
            )

        answer = " ".join(s for s in sentences if s)
        if len(answer) < 40:
            return (
                "The retrieved records do not contain enough evidence to answer this question; "
                "no conclusion is stated without supporting sources."
            )
        return answer

    def _actor_answer(self, context: LLMContext) -> str:
        """Who-questions: only report an actor when the records name one."""
        corpus_parts: List[str] = list(context.analysis.facts)
        corpus_parts.extend(context.analysis.blockers)
        corpus_parts.extend(context.analysis.decisions)
        for record in context.github_records + context.gmail_records:
            corpus_parts.append(record.text)
        match = self._ACTOR_EVIDENCE_RE.search(" ".join(corpus_parts))
        if match:
            return self._sentence(f"The available evidence identifies: {match.group(0)}")
        subject = context.project or "this project"
        return (
            f"The available evidence does not identify who is responsible for {subject}. "
            "The retrieved records describe requirements and current statuses only; "
            "no source names an approver or an executing person for this question."
        )


class OpenAICompatibleProvider(LLMProvider):
    """Minimal OpenAI-compatible chat completions provider over httpx (no SDK)."""

    def __init__(self, model: str, api_key: str, base_url: str, timeout: float) -> None:
        super().__init__()
        self.provider_name = "openai-compatible"
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def generate(self, prompt: LLMPrompt, context: LLMContext) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise LLMUnavailableError("httpx is not installed; HTTP LLM provider unavailable") from None

        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except LLMUnavailableError:
            raise
        except Exception as exc:
            raise LLMUnavailableError(sanitize_error(f"{type(exc).__name__}: {exc}")) from None

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMUnavailableError("HTTP LLM response is missing choices[0].message.content") from None
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailableError("HTTP LLM provider returned an empty completion")
        return content


# ------------------------------------------------------------------ factory

_http_cache: Dict[tuple, OpenAICompatibleProvider] = {}
_mock_provider = MockLLMProvider()


def get_llm_provider(name: Optional[str] = None) -> LLMProvider:
    """Resolve the configured provider; never raises for bad configuration."""
    resolved = resolve_llm_provider_name() if name is None else name.strip().lower()

    if resolved == DEFAULT_LLM_PROVIDER:
        return _mock_provider

    if resolved in HTTP_PROVIDER_NAMES:
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            return UnavailableLLMProvider(
                "LLM_PROVIDER selects an HTTP provider but LLM_API_KEY is not set. "
                "Set LLM_PROVIDER=mock for the built-in deterministic provider."
            )
        model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_HTTP_MODEL
        base_url = os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_HTTP_BASE_URL
        try:
            timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        except ValueError:
            timeout = 30.0
        cache_key = (model, base_url, timeout)
        provider = _http_cache.get(cache_key)
        if provider is None:
            provider = OpenAICompatibleProvider(model, api_key, base_url, timeout)
            _http_cache[cache_key] = provider
        return provider

    if resolved == "":
        return UnavailableLLMProvider(
            "LLM_PROVIDER is empty (configured off). Set LLM_PROVIDER=mock for the "
            "built-in deterministic provider or provide an HTTP provider configuration."
        )
    return UnavailableLLMProvider(
        f"Unknown LLM_PROVIDER {resolved!r}. Supported: {DEFAULT_LLM_PROVIDER!r} "
        f"or one of {', '.join(repr(n) for n in HTTP_PROVIDER_NAMES)}."
    )


def set_llm_provider(provider: Optional[LLMProvider]) -> None:
    """Test seam: replace the singleton mock provider instance."""
    global _mock_provider
    if provider is None:
        _mock_provider = MockLLMProvider()
    else:
        _mock_provider = provider


def build_llm_status() -> LLMStatus:
    """Honest status for GET /api/llm/status; never includes credentials."""
    resolved = resolve_llm_provider_name()

    if resolved == DEFAULT_LLM_PROVIDER:
        return LLMStatus(
            provider="mock",
            model=MOCK_MODEL,
            configured=True,
            status="healthy",
            message="Deterministic grounded mock provider; no external calls or API keys required.",
        )

    if resolved in HTTP_PROVIDER_NAMES:
        api_key = os.getenv("LLM_API_KEY", "").strip()
        model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_HTTP_MODEL
        if not api_key:
            return LLMStatus(
                provider=resolved,
                model=model,
                configured=False,
                status="unavailable",
                message="LLM_API_KEY is not set; the query pipeline will use the deterministic fallback.",
            )
        return LLMStatus(
            provider=resolved,
            model=model,
            configured=True,
            status="configured",
            message="HTTP provider configuration present; live connectivity is not tested by this status check.",
        )

    if resolved == "":
        return LLMStatus(
            provider="",
            model="",
            configured=False,
            status="unavailable",
            message="LLM_PROVIDER is empty; the query pipeline will use the deterministic fallback.",
        )

    return LLMStatus(
        provider=resolved,
        model="",
        configured=False,
        status="unavailable",
        message=f"Unknown LLM_PROVIDER {resolved!r}; the query pipeline will use the deterministic fallback.",
    )
