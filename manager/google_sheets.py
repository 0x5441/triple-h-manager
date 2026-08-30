import csv
import json
import re
import io
import zipfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree


REQUIRED_HEADERS = ("account", "title", "body")


class GoogleSheetStore:
    def __init__(self, spreadsheet_url, worksheet_name="إعلانات وايت حائل"):
        self.spreadsheet_id = self._extract_id(spreadsheet_url)
        self.worksheet_name = worksheet_name.strip() or "إعلانات وايت حائل"
        self.state_file = Path(__file__).resolve().parent / "data" / "published_rows.json"

    @staticmethod
    def _extract_id(value):
        value = str(value).strip()
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", value)
        spreadsheet_id = match.group(1) if match else value
        if not re.fullmatch(r"[a-zA-Z0-9_-]{20,}", spreadsheet_id):
            raise ValueError("رابط Google Sheets أو Spreadsheet ID غير صحيح")
        return spreadsheet_id

    def _published(self):
        if not self.state_file.exists():
            return set()
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return set(data if isinstance(data, list) else [])
        except (json.JSONDecodeError, OSError):
            return set()

    def sheet_names(self):
        url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/export?format=xlsx"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read("xl/workbook.xml")
            root = ElementTree.fromstring(xml)
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            names = [item.attrib["name"] for item in root.findall("x:sheets/x:sheet", namespace)]
            if not names:
                raise RuntimeError("لم توجد تبويبات")
            return names
        except Exception as exc:
            raise RuntimeError("تعذر جلب تبويبات الشيت العام") from exc
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return set(data if isinstance(data, list) else [])
        except (json.JSONDecodeError, OSError):
            return set()

    def rows(self):
        url = (f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/gviz/tq"
               f"?tqx=out:csv&sheet={quote(self.worksheet_name)}")
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8-sig")
        except Exception as exc:
            raise RuntimeError("تعذر قراءة الشيت. تأكد أن المشاركة: أي شخص لديه الرابط") from exc
        reader = csv.DictReader(text.splitlines())
        headers = [str(value).strip().lower() for value in (reader.fieldnames or [])]
        missing = [header for header in REQUIRED_HEADERS if header not in headers]
        if missing:
            found = ", ".join(headers) if headers else "لا توجد عناوين أعمدة"
            raise RuntimeError(
                f"أعمدة ناقصة في تبويب {self.worksheet_name}: {', '.join(missing)}. "
                f"الأعمدة المقروءة: {found}"
            )
        published = self._published()
        rows = []
        for row_number, values in enumerate(reader, start=2):
            normalized = {str(key).strip().lower(): value for key, value in values.items()}
            # normalize common alternative headers so matching uses 'account' and 'phone'
            account_candidates = [
                "account",
                "الحساب",
                "اسم الحساب",
                "account name",
                "username",
                "رقم الجوال",
                "phone",
                "phone number",
                "phone_number",
            ]
            phone_candidates = ["phone", "رقم الجوال", "mobile", "الهاتف"]
            if not normalized.get("account"):
                for cand in account_candidates:
                    if normalized.get(cand):
                        normalized["account"] = normalized.get(cand)
                        break
            if not normalized.get("phone"):
                for cand in phone_candidates:
                    if normalized.get(cand):
                        normalized["phone"] = normalized.get(cand)
                        break
            normalized.setdefault("phone", "966592099662")
            normalized.setdefault("image", "")
            normalized.setdefault("status", "")
            normalized["_row"] = row_number
            row_key = f"{self.spreadsheet_id}:{self.worksheet_name}:{row_number}"
            normalized["_key"] = row_key
            status = str(normalized.get("status", "")).strip().lower()
            if row_key not in published and status not in ("تم", "published", "done"):
                rows.append(normalized)
        return self.worksheet_name, rows, headers

    def mark(self, _worksheet, row_number, _status):
        published = self._published()
        published.add(f"{self.spreadsheet_id}:{self.worksheet_name}:{row_number}")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(sorted(published), ensure_ascii=False, indent=2), encoding="utf-8")
