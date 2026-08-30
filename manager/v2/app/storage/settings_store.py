"""Atomic JSON persistence for non-secret V2 settings."""

import json
import threading
from pathlib import Path

from app.config import SETTINGS_FILE
from app.models import AppSettings


class SettingsStoreError(RuntimeError):
    """Raised when local settings cannot be read or saved."""


class SettingsStore:
    def __init__(self, path: Path | str = SETTINGS_FILE) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def load(self) -> AppSettings:
        with self._lock:
            if not self.path.exists():
                return AppSettings()
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                return AppSettings.from_dict(payload)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise SettingsStoreError("تعذر قراءة إعدادات V2 المحلية") from exc

    def save(self, settings: AppSettings) -> AppSettings:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.tmp")
            try:
                temporary.write_text(
                    json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary.replace(self.path)
            except OSError as exc:
                raise SettingsStoreError("تعذر حفظ إعدادات V2 المحلية") from exc
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        return settings
