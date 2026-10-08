"""Shared test configuration (Step 8).

Isolates every test run from the persistent embedded Qdrant store:
tests always start with an empty, in-process in-memory vector store
behind an ephemeral temp directory - deterministic and side-effect free.
"""

import os
import sys
import tempfile
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Force in-memory/test mode before app.core.config is imported anywhere.
os.environ["QDRANT_URL"] = ""
os.environ["QDRANT_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="knowledgeops-rag-test-"), "qdrant"
)

from app.rag.qdrant_client import InMemoryVectorStore, set_vector_store  # noqa: E402

set_vector_store(InMemoryVectorStore())
