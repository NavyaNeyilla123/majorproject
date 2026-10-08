import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "KnowledgeOps AI API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Base path resolution: backend/ -> root -> data/
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_ROOT: Path = Path(os.getenv("DATA_ROOT", str(BASE_DIR / "data")))
    
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000"
    ]

    # --- RAG / Qdrant (Step 8) -------------------------------------------
    # QDRANT_URL empty -> embedded qdrant-client (persistent local storage).
    # QDRANT_URL set (e.g. http://localhost:6333) -> connect to that server.
    QDRANT_URL: str = os.getenv("QDRANT_URL", "").strip()
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "knowledgeops_projects")
    # Real-mode (MCP_PROVIDER=real) data is indexed into a separate collection
    # so the synthetic knowledgeops_projects index is never touched by real
    # ingestion, reindexing or clear operations.
    RAG_REAL_COLLECTION: str = os.getenv("RAG_REAL_COLLECTION", "knowledgeops_real")
    # Persistent storage for embedded mode (override with QDRANT_PATH).
    QDRANT_PATH: str = os.getenv(
        "QDRANT_PATH", str(BASE_DIR / ".rag_storage")
    )
    # Embedding layer: local deterministic implementation by default.
    # No external paid embedding API is required.
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local-hash")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "10"))

settings = Settings()
