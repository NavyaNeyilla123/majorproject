"""Embedding abstraction with a practical local default.

No external paid embedding API and no API keys: LocalHashEmbeddingProvider
builds deterministic feature-hashed vectors (unigrams + bigrams, sublinear
term frequency, L2-normalized) suitable for development and testing.

The provider is replaceable via the EMBEDDING_PROVIDER environment variable.
"""

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import Dict, List

from app.core.config import settings
from app.rag.models import RAGError

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Low-information tokens removed before scoring/embedding so ranking focuses
# on meaningful terms (question words, articles, auxiliaries).
STOPWORDS = frozenset(
    """
    a am an and are as at be been being but by did do does don for from had has
    have he her hers him his how i if in into is it its just may me might must
    my no nor not now of on or own same shall she so some such than that the
    their theirs them then there these they this those through to too under up
    very was we were what when where which while who whom why will with would
    you your yours can should need dare ought used
    """.split()
)


class EmbeddingProvider(ABC):
    """Abstraction over embedding implementations."""

    provider_name: str = "abstract"
    dim: int = 0

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


def tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens with stopwords removed."""
    return [
        token
        for token in _TOKEN_PATTERN.findall((text or "").lower())
        if token not in STOPWORDS
    ]


def _hash_feature(feature: str) -> tuple:
    digest = hashlib.md5(feature.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big")
    sign = 1.0 if digest[8] % 2 == 0 else -1.0
    return index, sign


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic feature-hashing embeddings (development/testing default)."""

    provider_name = "local-hash"

    def __init__(self, dim: int = None) -> None:
        self.dim = int(dim or settings.EMBEDDING_DIM)

    def embed_text(self, text: str) -> List[float]:
        vector = [0.0] * self.dim
        tokens = tokenize(text)
        if not tokens:
            return vector

        counts: Dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        for left, right in zip(tokens, tokens[1:]):
            bigram = f"{left}_{right}"
            counts[bigram] = counts.get(bigram, 0) + 1

        for feature, count in counts.items():
            index, sign = _hash_feature(feature)
            weight = 1.0 + math.log(count)  # sublinear term frequency
            vector[index % self.dim] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]


def get_embedding_provider(name: str = None, dim: int = None) -> EmbeddingProvider:
    resolved = (name or settings.EMBEDDING_PROVIDER).strip().lower()
    if resolved in ("local-hash", "local_hash", "hash"):
        return LocalHashEmbeddingProvider(dim=dim)
    raise RAGError(
        f"Unknown EMBEDDING_PROVIDER {resolved!r}. Supported: 'local-hash' "
        "(deterministic local embeddings; no external API required)."
    )
