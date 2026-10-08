"""Evidence validation and answer guards for the LLM layer (Step 9).

Three duties:
- validate_claims: a claim is supported only when every cited source exists in
  the retrieved records, the source types match, and the claim overlaps the
  record text (supporting evidence, no fabricated IDs).
- sanitize_answer: sentence-level removal of unsupported delay claims and
  unsupported execution claims, plus a case-insensitive forbidden-phrase scrub.
- constrain_confidence: min(evidence tier, LLM tier) with downgrades for
  rejected claims, low when evidence is weak, and high -> medium when the
  Analysis Agent recorded contradictions.
"""

import re
from typing import List, Optional, Tuple

from app.llm.models import EvidenceClaim, LLMResponse
from app.llm.prompt_builder import content_tokens, record_text

_FORBIDDEN_PHRASES = ["will definitely", "confirmed delay", "will be delayed"]
_FORBIDDEN_SUBSTITUTE = "is assessed as at risk (not confirmed)"

_DELAY_RE = re.compile(
    r"\bwill\s+be\s+delayed\b|\bwill\s+definitely\b|\bconfirmed\s+delay\b|"
    r"\b(?:is|are|was|were|has\s+been|have\s+been|will\s+be)\s+(?:delayed|postponed|deferred)\b|"
    r"\bdelayed\s+until\b",
    re.IGNORECASE,
)
_EXEC_RE = re.compile(
    r"\b(?:was|were|is|are|has\s+been|have\s+been|had\s+been|is\s+now)\s+"
    r"(assigned|approved|merged|resolved|executed|shipped|closed|completed|done|signed[\- ]off)\b",
    re.IGNORECASE,
)

_STATUS_SUPPORT = {
    "assigned": {"assigned"},
    "approved": {"approved"},
    "merged": {"merged"},
    "resolved": {"resolved"},
    "completed": {"completed", "done"},
    "done": {"completed", "done"},
    "shipped": {"shipped"},
    "closed": {"closed"},
    "signed off": {"signed_off", "signed-off"},
    "executed": {"executed"},
}

_MIN_ANSWER_CHARS = 40


def _sentence_split(answer: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [part for part in parts if part.strip()]


def _records_delay_evidence(records) -> bool:
    delay_claim = re.compile(
        r"\b(?:is|are|was|were|has\s+been|have\s+been|will\s+be)\s+"
        r"(?:delayed|postponed|deferred)\b",
        re.IGNORECASE,
    )
    return any(delay_claim.search(record_text(record)) for record in records)


def _verb_supported(verb: str, records) -> bool:
    verb = verb.lower().replace("-", " ")
    statuses = _STATUS_SUPPORT.get(verb, set())
    for record in records:
        data = getattr(record, "data", {}) or {}
        status = str(data.get("status") or "").lower()
        if status and status in statuses:
            return True
        if verb == "assigned" and data.get("security_reviewer_assigned"):
            return True
        if verb in ("executed", "completed", "done") and data.get(verb):
            return True
        if verb == "signed off" and (data.get("signed_off") or data.get("sign_off")):
            return True
        if verb == "approved" and data.get("approved"):
            return True
    return False


def sanitize_answer(answer: str, records) -> Tuple[str, List[str], List[str]]:
    """Remove unsupported delay/execution sentences and forbidden phrases.

    Returns (clean_answer, removed_sentences, notes). An empty clean_answer
    means nothing survived; the caller falls back to the deterministic answer.
    """
    if not answer or not answer.strip():
        return "", [], ["empty answer"]

    notes: List[str] = []
    removed: List[str] = []

    delay_supported = _records_delay_evidence(records)
    kept: List[str] = []
    for sentence in _sentence_split(answer):
        if _DELAY_RE.search(sentence) and not delay_supported:
            removed.append(sentence.strip())
            continue
        exec_match = _EXEC_RE.search(sentence)
        if exec_match and not _verb_supported(exec_match.group(1), records):
            removed.append(sentence.strip())
            continue
        kept.append(sentence)

    clean = " ".join(s.strip() for s in kept if s.strip())

    for phrase in _FORBIDDEN_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(clean):
            clean = pattern.sub(_FORBIDDEN_SUBSTITUTE, clean)
            notes.append(f"forbidden phrase scrubbed: {phrase}")

    clean = re.sub(r"\s+", " ", clean).strip()
    if removed:
        notes.append(f"{len(removed)} unsupported sentences removed")
    if len(clean) < _MIN_ANSWER_CHARS:
        notes.append("answer too short after validation")
        return "", removed, notes
    return clean, removed, notes


def validate_claims(claims: List[EvidenceClaim], records) -> Tuple[List[EvidenceClaim], List[EvidenceClaim]]:
    """Split claims into supported/rejected against the retrieved records."""
    by_id = {record.source_id: record for record in records}
    supported: List[EvidenceClaim] = []
    rejected: List[EvidenceClaim] = []

    for claim in claims:
        text = claim.claim.strip()
        if not text:
            claim.supported = False
            claim.rejection_reason = "empty claim"
            rejected.append(claim)
            continue
        if not claim.source_ids:
            claim.supported = False
            claim.rejection_reason = "claim cites no source_ids"
            rejected.append(claim)
            continue

        claim_tokens = content_tokens(text)
        reason = ""
        overlap = False
        for source_id in claim.source_ids:
            record = by_id.get(source_id)
            if record is None:
                reason = f"cited source {source_id!r} was not retrieved"
                break
            if claim.source_types:
                expected = {t.lower() for t in claim.source_types}
                if record.source.lower() not in expected and record.record_type.lower() not in expected:
                    reason = f"source_type mismatch for {source_id!r}"
                    break
            if claim_tokens and claim_tokens & content_tokens(record_text(record)):
                overlap = True
            elif not claim_tokens:
                reason = "claim has no content tokens to verify"
                break
        else:
            if not overlap:
                reason = "claim does not overlap the cited record text"

        if reason:
            claim.supported = False
            claim.rejection_reason = reason
            rejected.append(claim)
        else:
            claim.supported = True
            claim.rejection_reason = ""
            supported.append(claim)

    return supported, rejected


def _tier_index(tier: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(tier, 0)


def _downgrade(tier: str) -> str:
    return {"high": "medium", "medium": "low"}.get(tier, "low")


def constrain_confidence(
    raw_confidence: Optional[float],
    context,
    rejected_count: int = 0,
    dropped_items: int = 0,
) -> str:
    """Evidence-grounded confidence tier; never trusts the LLM number alone."""
    from app.agents.models import AgentContext  # noqa: F401  (lazy; type-check only)

    substantive = [r for r in context.retrieved_records if r.record_type != "cross_source_link"]
    sources = {r.source for r in substantive}
    if len(substantive) >= 3 and len(sources) >= 2:
        evidence_tier = "high"
    elif substantive:
        evidence_tier = "medium"
    else:
        evidence_tier = "low"

    if raw_confidence is None:
        llm_tier = evidence_tier
    elif raw_confidence >= 0.8:
        llm_tier = "high"
    elif raw_confidence >= 0.5:
        llm_tier = "medium"
    else:
        llm_tier = "low"

    tier = evidence_tier if _tier_index(evidence_tier) <= _tier_index(llm_tier) else llm_tier

    if rejected_count > 0 or dropped_items > 0:
        tier = _downgrade(tier)
    if not substantive or not context.facts:
        tier = "low"
    if context.contradictions and tier == "high":
        tier = "medium"
    return tier


def sanitize_llm_actions(actions: List[str]) -> List[str]:
    """Keep LLM-suggested actions as clean recommendations: non-empty, deduped,
    no forbidden claim phrases, no past-execution claims (recommendation != done)."""
    clean: List[str] = []
    for action in actions:
        text = re.sub(r"\s+", " ", str(action or "")).strip()
        if not text:
            continue
        lowered = text.lower()
        if any(phrase in lowered for phrase in _FORBIDDEN_PHRASES):
            continue
        if _EXEC_RE.search(text):
            continue
        if text not in clean:
            clean.append(text)
        if len(clean) >= 10:
            break
    return clean


def drop_unsupported_list_items(response: LLMResponse, context) -> int:
    """Cross-check LLM list restatements against Analysis output; drop mismatches."""
    def matches(item: str, known: List[str]) -> bool:
        needle = re.sub(r"[^a-z0-9 ]+", "", item.lower()).strip()
        if not needle:
            return False
        for entry in known:
            haystack = re.sub(r"[^a-z0-9 ]+", "", entry.lower()).strip()
            if needle in haystack or haystack in needle:
                return True
        return False

    dropped = 0
    for attr, known in (
        ("risks", context.risks),
        ("blockers", context.blockers),
        ("decisions", context.decisions),
    ):
        items: List[str] = getattr(response, attr)
        kept = []
        for item in items:
            if matches(item, known):
                kept.append(item)
            else:
                dropped += 1
        setattr(response, attr, kept)
    return dropped
