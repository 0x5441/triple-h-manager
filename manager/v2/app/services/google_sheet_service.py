"""Public Google Sheet reader independent from browser automation."""

import csv
import hashlib
import io
import re
import zipfile
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.models import Account, Advertisement
from app.storage import ProcessedRowStore
from app.storage.account_store import normalize_username


REQUIRED_COLUMNS = ("account", "title", "body")
OPTIONAL_COLUMNS = ("phone", "image", "status")


class GoogleSheetError(RuntimeError):
    """Base error for public Google Sheet operations."""


class InvalidGoogleSheetUrlError(GoogleSheetError):
    """Raised when a link or spreadsheet id is malformed."""


class GoogleSheetAccessError(GoogleSheetError):
    """Raised when public export data cannot be fetched or decoded."""


class WorksheetNotFoundError(GoogleSheetError):
    """Raised when the requested visible worksheet is absent."""


class MissingColumnsError(GoogleSheetError):
    """Raised when account, title, or body is missing from the header."""


@dataclass(slots=True)
class SheetReadResult:
    spreadsheet_id: str
    worksheet: str
    advertisements: list[Advertisement] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    ignored_completed: int = 0
    ignored_processed: int = 0
    unmatched_rows: int = 0
    invalid_rows: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "spreadsheet_id": self.spreadsheet_id,
            "worksheet": self.worksheet,
            "headers": list(self.headers),
            "counts": {
                "advertisements": len(self.advertisements),
                "ignored_completed": self.ignored_completed,
                "ignored_processed": self.ignored_processed,
                "unmatched_rows": self.unmatched_rows,
                "invalid_rows": self.invalid_rows,
            },
            "advertisements": [
                {
                    "id": advertisement.id,
                    "account_id": advertisement.account_id,
                    "title": advertisement.title,
                    "body": advertisement.body,
                    "phone": advertisement.phone,
                    "image": advertisement.image,
                    "source_key": advertisement.source_key,
                }
                for advertisement in self.advertisements
            ],
        }


def _default_fetcher(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Triple-H-Manager-V2/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


class GoogleSheetService:
    def __init__(
        self,
        processed_store: ProcessedRowStore,
        *,
        fetcher: Callable[[str], bytes] = _default_fetcher,
    ) -> None:
        self._processed = processed_store
        self._fetcher = fetcher

    @staticmethod
    def extract_spreadsheet_id(value: str) -> str:
        candidate = str(value).strip()
        match = re.fullmatch(
            r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)(?:/[^?#]*)?(?:\?[^#]*)?(?:#.*)?",
            candidate,
        )
        spreadsheet_id = match.group(1) if match else candidate
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", spreadsheet_id):
            raise InvalidGoogleSheetUrlError("Google Sheet URL or spreadsheet id is invalid")
        return spreadsheet_id

    def get_sheet_names(self, spreadsheet_url: str) -> list[str]:
        spreadsheet_id = self.extract_spreadsheet_id(spreadsheet_url)
        export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
        try:
            content = self._fetcher(export_url)
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                workbook_xml = archive.read("xl/workbook.xml")
            root = ElementTree.fromstring(workbook_xml)
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            names = [
                sheet.attrib["name"]
                for sheet in root.findall("x:sheets/x:sheet", namespace)
                if sheet.attrib.get("state", "visible") == "visible"
            ]
        except Exception as exc:
            raise GoogleSheetAccessError(
                "Sheet tabs could not be fetched; verify that the sheet is public"
            ) from exc
        if not names:
            raise GoogleSheetAccessError("The spreadsheet has no visible worksheets")
        return names

    def read_worksheet(
        self,
        spreadsheet_url: str,
        worksheet: str,
        accounts: Sequence[Account],
    ) -> SheetReadResult:
        spreadsheet_id = self.extract_spreadsheet_id(spreadsheet_url)
        worksheet_name = str(worksheet).strip()
        if not worksheet_name:
            raise WorksheetNotFoundError("Worksheet name must not be empty")
        names = self.get_sheet_names(spreadsheet_id)
        if worksheet_name not in names:
            raise WorksheetNotFoundError(f"Worksheet not found: {worksheet_name}")

        csv_url = (
            f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
            f"?tqx=out:csv&headers=1&sheet={quote(worksheet_name)}"
        )
        try:
            text = self._fetcher(csv_url).decode("utf-8-sig")
        except Exception as exc:
            raise GoogleSheetAccessError(
                f"Worksheet could not be read: {worksheet_name}"
            ) from exc

        reader = csv.DictReader(io.StringIO(text))
        original_headers = reader.fieldnames or []
        headers = [str(header).strip().casefold() for header in original_headers]
        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            found = ", ".join(headers) if headers else "none"
            raise MissingColumnsError(
                f"Missing required columns: {', '.join(missing)}. Found: {found}"
            )

        result = SheetReadResult(spreadsheet_id, worksheet_name, headers=headers)
        occurrences: Counter[str] = Counter()
        processed_keys = self._processed.list_keys()
        for raw_row in reader:
            normalized = {
                str(key).strip().casefold(): str(value or "").strip()
                for key, value in raw_row.items()
                if key is not None
            }
            row = {column: normalized.get(column, "") for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}
            if row["status"] == "تم":
                result.ignored_completed += 1
                continue

            content_fingerprint = self._content_fingerprint(row)
            occurrences[content_fingerprint] += 1
            source_key = self._source_key(
                spreadsheet_id,
                worksheet_name,
                content_fingerprint,
                occurrences[content_fingerprint],
            )
            if source_key in processed_keys:
                result.ignored_processed += 1
                continue

            account = self._match_account(row["account"], accounts)
            if account is None:
                result.unmatched_rows += 1
                continue
            if not row["title"] or not row["body"]:
                result.invalid_rows += 1
                continue

            result.advertisements.append(
                Advertisement(
                    id=f"sheet-{source_key[:24]}",
                    account_id=account.id,
                    title=row["title"],
                    body=row["body"],
                    phone=row["phone"],
                    image=row["image"],
                    source_key=source_key,
                )
            )
        return result

    def mark_processed(self, advertisement: Advertisement) -> None:
        if not advertisement.source_key:
            raise ValueError("Advertisement has no Google Sheet source key")
        self._processed.mark_processed(advertisement.source_key)

    @staticmethod
    def _match_account(value: str, accounts: Sequence[Account]) -> Account | None:
        normalized_value = str(value).strip()
        if not normalized_value:
            return None
        username_value = normalize_username(normalized_value)
        username_matches = [
            account
            for account in accounts
            if normalize_username(account.username) == username_value
        ]
        if len(username_matches) == 1:
            return username_matches[0]
        name_value = normalized_value.casefold()
        name_matches = [account for account in accounts if account.name.strip().casefold() == name_value]
        return name_matches[0] if len(name_matches) == 1 else None

    @staticmethod
    def _content_fingerprint(row: dict[str, str]) -> str:
        canonical = "\0".join(row[column] for column in REQUIRED_COLUMNS + ("phone", "image"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_key(
        spreadsheet_id: str,
        worksheet: str,
        content_fingerprint: str,
        occurrence: int,
    ) -> str:
        canonical = f"{spreadsheet_id}\0{worksheet}\0{content_fingerprint}\0{occurrence}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
