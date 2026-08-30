import json
from pathlib import Path

from cryptography.fernet import Fernet

from app.storage.migration import build_migration_preview, read_legacy_records


def test_legacy_migration_preview_is_read_only(tmp_path: Path) -> None:
    key_path = tmp_path / ".secret.key"
    accounts_path = tmp_path / "accounts.enc"
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    legacy = [{"name": "قديم", "username": "0500000000", "password": "secret", "ads": []}]
    accounts_path.write_bytes(Fernet(key).encrypt(json.dumps(legacy).encode()))
    before = accounts_path.read_bytes()

    records = read_legacy_records(accounts_path, key_path)
    preview = build_migration_preview(
        records,
        id_factory=lambda: "stable-account-id",
        timestamp_factory=lambda: "2026-08-30T10:00:00+03:00",
    )

    assert preview[0].id == "stable-account-id"
    assert preview[0].username == "0500000000"
    assert accounts_path.read_bytes() == before
