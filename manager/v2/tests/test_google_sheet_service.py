import io
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from app.models import Account
from app.services import (
    GoogleSheetService,
    InvalidGoogleSheetUrlError,
    MissingColumnsError,
    WorksheetNotFoundError,
)
from app.storage import ProcessedRowStore


SPREADSHEET_ID = "1abcdefghijklmnopqrstuvwxyzABCDEFGHIJK"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit?gid=0"


def workbook_bytes(names: list[str]) -> bytes:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" state="visible" '
        f'r:id="rId{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/workbook.xml", xml)
    return output.getvalue()


class FakeSheetFetcher:
    def __init__(self, csv_text: str, names: list[str] | None = None) -> None:
        self.csv_text = csv_text
        self.names = names or ["Ads"]
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if "format=xlsx" in url:
            return workbook_bytes(self.names)
        return self.csv_text.encode("utf-8")


def accounts() -> list[Account]:
    return [
        Account("account-1", "الحساب الأول", "0500000000", "secret"),
        Account("account-2", "الحساب الثاني", "0500000001", "secret"),
    ]


def make_service(tmp_path: Path, fetcher: FakeSheetFetcher) -> GoogleSheetService:
    return GoogleSheetService(
        ProcessedRowStore(tmp_path / "published_rows.json"),
        fetcher=fetcher,
    )


def test_extracts_spreadsheet_id_from_public_url_or_direct_id() -> None:
    assert GoogleSheetService.extract_spreadsheet_id(SHEET_URL) == SPREADSHEET_ID
    assert GoogleSheetService.extract_spreadsheet_id(SPREADSHEET_ID) == SPREADSHEET_ID

    with pytest.raises(InvalidGoogleSheetUrlError):
        GoogleSheetService.extract_spreadsheet_id("https://example.com/not-a-sheet")


def test_gets_visible_sheet_names_from_fake_xlsx(tmp_path: Path) -> None:
    fetcher = FakeSheetFetcher("", names=["Ads", "إعلانات حائل"])
    service = make_service(tmp_path, fetcher)

    assert service.get_sheet_names(SHEET_URL) == ["Ads", "إعلانات حائل"]
    assert fetcher.urls[0].endswith("/export?format=xlsx")


def test_reads_matches_and_filters_csv_rows(tmp_path: Path) -> None:
    csv_text = """account,title,body,phone,image,status
الحساب الأول,عنوان 1,نص 1,0500000000,,
050-000-0001,عنوان 2,نص 2,,https://example.com/image.jpg,
الحساب الأول,مكتمل,لن يقرأ,,,تم
حساب غير معروف,غير مطابق,نص,,,
الحساب الأول,,نص ناقص,,,
"""
    fetcher = FakeSheetFetcher(csv_text)
    service = make_service(tmp_path, fetcher)

    result = service.read_worksheet(SHEET_URL, "Ads", accounts())

    assert "headers=1" in fetcher.urls[-1]
    assert [advertisement.account_id for advertisement in result.advertisements] == [
        "account-1",
        "account-2",
    ]
    assert result.advertisements[0].phone == "0500000000"
    assert result.advertisements[1].image == "https://example.com/image.jpg"
    assert result.ignored_completed == 1
    assert result.unmatched_rows == 1
    assert result.invalid_rows == 1


def test_optional_columns_may_be_absent(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        FakeSheetFetcher("account,title,body\nالحساب الأول,عنوان,نص\n"),
    )

    result = service.read_worksheet(SHEET_URL, "Ads", accounts())

    assert len(result.advertisements) == 1
    assert result.advertisements[0].phone == ""
    assert result.advertisements[0].image == ""


def test_marked_advertisement_is_skipped_on_next_read(tmp_path: Path) -> None:
    fetcher = FakeSheetFetcher("account,title,body\nالحساب الأول,عنوان,نص\n")
    service = make_service(tmp_path, fetcher)
    first = service.read_worksheet(SHEET_URL, "Ads", accounts())

    service.mark_processed(first.advertisements[0])
    second = service.read_worksheet(SHEET_URL, "Ads", accounts())

    assert second.advertisements == []
    assert second.ignored_processed == 1


def test_source_key_is_stable_when_unrelated_row_is_inserted(tmp_path: Path) -> None:
    fetcher = FakeSheetFetcher("account,title,body\nالحساب الأول,عنوان ثابت,نص ثابت\n")
    service = make_service(tmp_path, fetcher)
    before = service.read_worksheet(SHEET_URL, "Ads", accounts()).advertisements[0].source_key
    fetcher.csv_text = (
        "account,title,body\n"
        "حساب غير معروف,صف جديد,نص\n"
        "الحساب الأول,عنوان ثابت,نص ثابت\n"
    )

    after = service.read_worksheet(SHEET_URL, "Ads", accounts()).advertisements[0].source_key

    assert after == before


def test_reports_missing_worksheet_and_required_columns(tmp_path: Path) -> None:
    service = make_service(tmp_path, FakeSheetFetcher("account,title\nالحساب الأول,عنوان\n"))

    with pytest.raises(WorksheetNotFoundError, match="Missing"):
        service.read_worksheet(SHEET_URL, "Missing", accounts())

    with pytest.raises(MissingColumnsError, match="body"):
        service.read_worksheet(SHEET_URL, "Ads", accounts())
