import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.archivist.interface import Archivist


class JsonlArchivist(Archivist):
    """Writes run results to a local JSONL file."""

    def __init__(self, filepath: Optional[str] = None) -> None:
        self.filepath = Path(filepath or "backend/runs.jsonl")

    def store_run(self, payload: Dict[str, Any]) -> Dict[str, str]:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        archive_ref = payload.get("run_id") or str(uuid.uuid4())
        stored_at = int(time.time())
        
        record = {
            **payload,
            "stored_at": stored_at,
            "archive_ref": archive_ref
        }
        
        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        
        return {"archive_ref": archive_ref}


