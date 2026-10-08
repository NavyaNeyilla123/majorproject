from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def get_health():
    return {
        "status": "healthy",
        "service": "KnowledgeOps AI API",
        "version": "1.0.0"
    }
