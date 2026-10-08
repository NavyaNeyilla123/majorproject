import json
from pathlib import Path
from typing import Any
from app.core.config import settings

class DataLoader:
    """Helper for reading raw JSON datasets from the data directory."""
    
    @staticmethod
    def load_json(relative_path: str) -> Any:
        path = settings.DATA_ROOT / relative_path
        if not path.exists():
            # Fallback path lookup in case CWD is backend/
            alt_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / relative_path
            if alt_path.exists():
                path = alt_path
            else:
                raise FileNotFoundError(f"Data file not found at: {path} or {alt_path}")
                
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

data_loader = DataLoader()
