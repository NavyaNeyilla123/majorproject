"""Provider abstraction for the LLM layer (Step 9)."""

from abc import ABC, abstractmethod

from app.llm.models import LLMContext, LLMPrompt, LLMResponse


class LLMProvider(ABC):
    """Minimal seam: every provider turns a grounded prompt into text output.

    ``generate_structured`` parses that text into an LLMResponse; providers
    may return either raw text or a JSON object as their text output.
    """

    provider_name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(self, prompt: LLMPrompt, context: LLMContext) -> str:
        """Return the raw provider output for the given grounded prompt."""

    def generate_structured(self, prompt: LLMPrompt, context: LLMContext) -> LLMResponse:
        from app.llm.response_parser import parse_response

        raw = self.generate(prompt, context)
        return parse_response(raw)
