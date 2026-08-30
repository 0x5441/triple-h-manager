import json
from pathlib import Path

from app.storage import ProcessedRowStore


def test_processed_row_store_persists_unique_keys(tmp_path: Path) -> None:
    path = tmp_path / "published_rows.json"
    store = ProcessedRowStore(path)

    store.mark_processed("stable-key")
    store.mark_processed("stable-key")

    assert ProcessedRowStore(path).list_keys() == {"stable-key"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {"schema_version": 1, "processed_keys": ["stable-key"]}
