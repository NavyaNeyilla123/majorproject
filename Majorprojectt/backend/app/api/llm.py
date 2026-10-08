from fastapi import APIRouter

from app.llm import LLMStatus, build_llm_status

router = APIRouter()


@router.get("/llm/status", response_model=LLMStatus)
def get_llm_status() -> LLMStatus:
    """Honest LLM provider status.

    Never exposes credentials and never claims connectivity: an HTTP provider
    with a key present reports 'configured' (untested), not 'healthy'.
    """
    return build_llm_status()
