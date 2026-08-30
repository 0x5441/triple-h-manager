from pathlib import Path

import pytest

from app.services import SettingsService
from app.storage import SettingsStore, SettingsStoreError


def test_settings_service_round_trip(tmp_path: Path) -> None:
    service = SettingsService(SettingsStore(tmp_path / "settings.json"))

    saved = service.save(
        spreadsheet_url=" https://docs.google.com/spreadsheets/d/example ",
        worksheet=" Ads ",
        default_phone=" 0500000000 ",
        headless=True,
    )
    loaded = service.load()

    assert loaded == saved
    assert loaded.worksheet == "Ads"
    assert loaded.default_phone == "0500000000"
    assert loaded.headless is True


def test_settings_store_reports_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(SettingsStoreError, match="تعذر قراءة"):
        SettingsStore(path).load()
