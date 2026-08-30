"""Settings API used by controllers and UI without direct file access."""

from app.models import AppSettings
from app.storage.settings_store import SettingsStore


class SettingsService:
    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def load(self) -> AppSettings:
        return self._store.load()

    def save(
        self,
        *,
        spreadsheet_url: str,
        worksheet: str,
        default_phone: str,
        headless: bool,
    ) -> AppSettings:
        settings = AppSettings(
            spreadsheet_url=spreadsheet_url,
            worksheet=worksheet,
            default_phone=default_phone,
            headless=headless,
        )
        return self._store.save(settings)
