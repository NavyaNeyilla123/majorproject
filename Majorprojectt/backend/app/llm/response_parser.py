"""Parses provider text output into a structured LLMResponse (Step 9).

Malformed output never reaches the API layer: missing/empty answers and
unparseable payloads raise LLMParseError so the pipeline can fall back.
"""

import json
import re
from typing import Any, Dict, List

from app.llm.models import (
    LLMParseError,
    LLMResponse,
    EvidenceClaim,
    clamp_confidence,
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json(raw: Any) -> Dict[str, Any]:
    """Extract a JSON object from raw provider text (bare, fenced, or embedded)."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise LLMParseError("provider returned empty output")

    text = raw.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise LLMParseError("provider returned JSON that is not an object")
    except json.JSONDecodeError:
        pass

    fence = _FENCE_RE.search(text)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise LLMParseError("provider output does not contain a valid JSON object")


def _str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for entry in value:
        text = str(entry).strip() if entry is not None else ""
        if text and text not in items:
            items.append(text)
    return items


def _parse_claims(value: Any) -> List[EvidenceClaim]:
    if not isinstance(value, list):
        return []
    claims: List[EvidenceClaim] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("claim") or "").strip()
        if not text:
            continue
        claims.append(
            EvidenceClaim(
                claim=text,
                source_ids=_str_list(entry.get("source_ids")),
                source_types=_str_list(entry.get("source_types")),
                confidence=clamp_confidence(entry.get("confidence"), 0.5),
            )
        )
    return claims


def parse_response(raw: Any) -> LLMResponse:
    """Parse provider output into LLMResponse, raising LLMParseError on any gap."""
    data = extract_json(raw)

    answer = str(data.get("answer") or "").strip()
    if not answer:
        raise LLMParseError("provider response is missing a non-empty 'answer'")

    return LLMResponse(
        answer=answer,
        risks=_str_list(data.get("risks")),
        blockers=_str_list(data.get("blockers")),
        decisions=_str_list(data.get("decisions")),
        recommended_actions=_str_list(data.get("recommended_actions")),
        evidence_claims=_parse_claims(data.get("evidence_claims")),
        confidence=clamp_confidence(data.get("confidence"), 0.5),
    )
