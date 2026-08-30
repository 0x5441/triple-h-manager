"""User-editable V2 application settings."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class AppSettings:
    spreadsheet_url: str = ""
    worksheet: str = ""
    default_phone: str = ""
    headless: bool = False

    def __post_init__(self) -> None:
        self.spreadsheet_url = self.spreadsheet_url.strip()
        self.worksheet = self.worksheet.strip()
        self.default_phone = self.default_phone.strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        if not isinstance(data, dict):
            return cls()
        return cls(
            spreadsheet_url=str(data.get("spreadsheet_url", "")),
            worksheet=str(data.get("worksheet", "")),
            default_phone=str(data.get("default_phone", "")),
            headless=bool(data.get("headless", False)),
        )
