"""LLM Agent stage (Step 9): grounded generation with validation and fallback.

Runs after Analysis and before Workflow. The agent never fails the pipeline:
any provider, parsing or validation problem falls back to the deterministic
compose_final_answer() and records why in the stage detail.
"""

import re
from typing import Optional

from app.agents.analysis_agent import compose_final_answer
from app.agents.base_agent import BaseAgent
from app.agents.models import AgentContext, AnalysisClaim
from app.llm import (
    LLMParseError,
    LLMProvider,
    build_llm_context,
    build_prompt,
    constrain_confidence,
    drop_unsupported_list_items,
    get_llm_provider,
    sanitize_answer,
    sanitize_llm_actions,
    validate_claims,
)

_DETAIL_ERROR_CHARS = 160


class LLMAgent(BaseAgent):
    """Generates the final answer from grounded context via the configured provider."""

    name = "LLM Agent"

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        super().__init__()
        self._provider_override = provider
        self.provider: Optional[LLMProvider] = provider

    def execute(self, context: AgentContext) -> AgentContext:
        try:
            provider = self._provider_override or get_llm_provider()
            self.provider = provider
            llm_context = build_llm_context(context)
            prompt = build_prompt(llm_context)
            response = provider.generate_structured(prompt, llm_context)
        except Exception as exc:
            return self._fallback(context, exc)

        try:
            supported, rejected = validate_claims(response.evidence_claims, context.retrieved_records)
            dropped = drop_unsupported_list_items(response, context)
            response.recommended_actions = sanitize_llm_actions(response.recommended_actions)
            clean, _removed, notes = sanitize_answer(response.answer, context.retrieved_records)
            if not clean:
                raise LLMParseError("; ".join(notes) or "answer removed by validation guards")

            final_confidence = constrain_confidence(
                response.confidence,
                context,
                rejected_count=len(rejected) + dropped,
                dropped_items=dropped,
            )
        except Exception as exc:
            return self._fallback(context, exc)

        response.answer = clean
        response.evidence_claims = supported + rejected
        context.llm_response = response
        context.llm_used = True
        context.final_answer = clean
        context.confidence = final_confidence

        for claim in supported:
            if not any(existing.claim == claim.claim for existing in context.claims):
                context.claims.append(
                    AnalysisClaim(
                        claim=claim.claim,
                        kind="llm",
                        confidence=final_confidence,
                        source_ids=list(claim.source_ids),
                    )
                )
        for claim in context.claims:
            claim.confidence = final_confidence

        detail_parts = [
            f"{provider.provider_name} · grounded response",
            f"claims {len(supported)} supported / {len(rejected)} rejected",
        ]
        if dropped:
            detail_parts.append(f"{dropped} list items dropped")
        detail_parts.append(
            f"confidence {response.confidence:.2f} → {final_confidence}"
        )
        if notes:
            detail_parts.append(" · ".join(notes))
        self.detail = " · ".join(detail_parts)
        return context

    def _fallback(self, context: AgentContext, exc: Exception) -> AgentContext:
        """Deterministic answer + honest reason; never raises."""
        message = str(exc) or exc.__class__.__name__
        message = re.sub(r"\s+", " ", message)[:_DETAIL_ERROR_CHARS]
        context.final_answer = compose_final_answer(context)
        context.llm_used = False
        context.llm_response = None
        context.confidence = constrain_confidence(None, context, rejected_count=0)
        self.detail = (
            f"llm unavailable ({type(exc).__name__}: {message}) · deterministic fallback"
        )
        return context
