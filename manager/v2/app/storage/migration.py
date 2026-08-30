"""Read-only helpers for planning migration from the legacy account store."""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from app.models import Account, AccountStatus
from app.storage.account_store import AccountStoreCorruptedError


def read_legacy_records(accounts_path: Path | str, key_path: Path | str) -> list[dict[str, Any]]:
    """Decrypt legacy records without writing to either legacy or V2 storage."""
    try:
        cipher = Fernet(Path(key_path).read_bytes())
        payload = json.loads(cipher.decrypt(Path(accounts_path).read_bytes()).decode("utf-8"))
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError("Legacy account payload must be a list of objects")
        return payload
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError, OSError) as exc:
        raise AccountStoreCorruptedError("Legacy account data could not be read") from exc


def build_migration_preview(
    records: list[dict[str, Any]],
    *,
    id_factory: Callable[[], str] = lambda: str(uuid4()),
    timestamp_factory: Callable[[], str] = lambda: datetime.now().astimezone().isoformat(timespec="seconds"),
) -> list[Account]:
    """Convert legacy dictionaries in memory; this function never persists them."""
    preview: list[Account] = []
    for record in records:
        timestamp = timestamp_factory()
        paused = bool(record.get("paused", False))
        preview.append(
            Account(
                id=id_factory(),
                name=str(record.get("name", "")),
                username=str(record.get("username", "")),
                password=str(record.get("password", "")),
                paused=paused,
                last_status=AccountStatus.PAUSED if paused else AccountStatus.NEVER_RUN,
                last_run_at=str(record.get("last_run_at", "")),
                ads=list(record.get("ads", [])),
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return preview
