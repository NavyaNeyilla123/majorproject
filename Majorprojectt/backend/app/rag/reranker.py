"""Deterministic, lightweight reranker (no LLM - that is a later step).

Improves ordering using: the hybrid score, title/query term overlap, and
whether the full query phrase appears in the content. Scores are normalized,
explainable and stable across runs.
"""

import re
from typing import List, Optional

from app.rag.embeddings import tokenize
from app.rag.models import RetrievedChunk

_PHRASE_GAP = re.compile(r"\s+")

# Chunks added through relationship expansion (linked to a top candidate)
# receive a fixed, explainable bonus so linked evidence is not out-ranked
# by weakly-matching records.
LINKED_BONUS = 0.12


def normalize_query(text: str) -> str:
    return _PHRASE_GAP.sub(" ", (text or "").strip().lower())


class Reranker:
    """Re-scores retrieved chunks with explainable, deterministic rules."""

    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        filters: Optional[dict] = None,
    ) -> List[RetrievedChunk]:
        query_tokens = set(tokenize(query))
        query_normalized = normalize_query(query)
        project_filter = (filters or {}).get("project_id", "")

        for chunk in chunks:
            title_tokens = set(tokenize(chunk.title))
            content_normalized = normalize_query(chunk.content)

            title_overlap = (
                len(query_tokens & title_tokens) / len(query_tokens)
                if query_tokens
                else 0.0
            )
            phrase_bonus = 0.0
            if query_normalized and query_normalized in content_normalized:
                phrase_bonus = 1.0
            elif query_normalized:
                # Partial phrase coverage: fraction of query tokens co-occurring
                # in the content (proxy for topical match).
                content_tokens = set(tokenize(chunk.content))
                coverage = (
                    len(query_tokens & content_tokens) / len(query_tokens)
                    if query_tokens
                    else 0.0
                )
                phrase_bonus = round(coverage, 4)

            project_bonus = 0.0
            if project_filter:
                project_bonus = 1.0 if chunk.project_id == project_filter else 0.0
            elif chunk.project_id:
                project_bonus = 0.5

            base = chunk.score
            linked_from = str(chunk.metadata.get("expanded_from") or "")
            rerank_score = (
                0.70 * base
                + 0.15 * title_overlap
                + 0.10 * phrase_bonus
                + 0.05 * project_bonus
                + (LINKED_BONUS if linked_from else 0.0)
            )
            chunk.rerank_score = round(rerank_score, 6)
            reasons = [f"hybrid={base:.4f}"]
            if linked_from:
                reasons.append(f"linked_to:{linked_from}")
            if title_overlap > 0:
                reasons.append(f"title_overlap={title_overlap:.2f}")
            if phrase_bonus > 0:
                reasons.append(f"query_coverage={phrase_bonus:.2f}")
            if project_bonus > 0:
                reasons.append("project_match" if project_filter else "project_present")
            chunk.rerank_reasons = reasons

        chunks.sort(key=lambda c: (-c.rerank_score, c.chunk_id))
        return chunks
