"""LLM integration layer (Step 9).

Public surface: provider abstraction + factory, prompt/context builders,
response parsing, evidence validation and honest status reporting.
"""

from app.llm.base import LLMProvider
from app.llm.models import (
    EvidenceClaim,
    LLMAnalysisSection,
    LLMClaim,
    LLMContext,
    LLMError,
    LLMParseError,
    LLMPrompt,
    LLMRecord,
    LLMResponse,
    LLMStatus,
    LLMUnavailableError,
)
from app.llm.prompt_builder import build_llm_context, build_prompt, content_tokens, record_text
from app.llm.provider import (
    DEFAULT_LLM_PROVIDER,
    HTTP_PROVIDER_NAMES,
    MOCK_MODEL,
    MockLLMProvider,
    OpenAICompatibleProvider,
    UnavailableLLMProvider,
    build_llm_status,
    get_llm_provider,
    resolve_llm_provider_name,
    sanitize_error,
    set_llm_provider,
)
from app.llm.response_parser import extract_json, parse_response
from app.llm.validator import (
    constrain_confidence,
    drop_unsupported_list_items,
    sanitize_answer,
    sanitize_llm_actions,
    validate_claims,
)

__all__ = [
    "DEFAULT_LLM_PROVIDER",
    "HTTP_PROVIDER_NAMES",
    "MOCK_MODEL",
    "EvidenceClaim",
    "LLMAnalysisSection",
    "LLMClaim",
    "LLMContext",
    "LLMError",
    "LLMParseError",
    "LLMPrompt",
    "LLMProvider",
    "LLMRecord",
    "LLMResponse",
    "LLMStatus",
    "LLMUnavailableError",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "UnavailableLLMProvider",
    "build_llm_context",
    "build_llm_status",
    "build_prompt",
    "constrain_confidence",
    "content_tokens",
    "drop_unsupported_list_items",
    "extract_json",
    "get_llm_provider",
    "parse_response",
    "record_text",
    "resolve_llm_provider_name",
    "sanitize_answer",
    "sanitize_error",
    "sanitize_llm_actions",
    "set_llm_provider",
    "validate_claims",
]
