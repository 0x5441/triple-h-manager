"""Local processed-row keys for public read-only Google Sheets."""

import json
import threading
from pathlib import Path

from app.config import PUBLISHED_ROWS_FILE


class ProcessedRowStoreError(RuntimeError):
    """Raised when local processed-row state cannot be read or saved."""


class ProcessedRowStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str = PUBLISHED_ROWS_FILE) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def list_keys(self) -> set[str]:
        with self._lock:
            if not self.path.exists():
                return set()
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or payload.get("schema_version") != self.SCHEMA_VERSION:
                    raise ValueError("Unsupported processed-row schema")
                keys = payload.get("processed_keys")
                if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
                    raise ValueError("processed_keys must be a list of strings")
                return set(keys)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ProcessedRowStoreError("Local processed-row state could not be read") from exc

    def is_processed(self, key: str) -> bool:
        return key in self.list_keys()

    def mark_processed(self, key: str) -> None:
        normalized = str(key).strip()
        if not normalized:
            raise ValueError("Processed-row key must not be empty")
        with self._lock:
            keys = self.list_keys()
            keys.add(normalized)
            payload = {
                "schema_version": self.SCHEMA_VERSION,
                "processed_keys": sorted(keys),
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary.replace(self.path)
            except OSError as exc:
                raise ProcessedRowStoreError("Local processed-row state could not be saved") from exc
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
