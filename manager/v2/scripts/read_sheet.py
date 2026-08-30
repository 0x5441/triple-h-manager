"""Read-only CLI for listing public Google Sheet tabs and matched ads."""

import argparse
import json
import sys

from app.services import GoogleSheetError, GoogleSheetService
from app.storage import AccountStore, ProcessedRowStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a public Google Sheet without publishing ads.")
    parser.add_argument("--url", required=True, help="Public Google Sheet URL or spreadsheet id")
    parser.add_argument("--worksheet", help="Worksheet to read; omit to list tabs only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = GoogleSheetService(ProcessedRowStore())
    try:
        sheet_names = service.get_sheet_names(args.url)
        output: dict[str, object] = {"worksheets": sheet_names}
        if args.worksheet:
            accounts = AccountStore().list_accounts()
            result = service.read_worksheet(args.url, args.worksheet, accounts)
            output["result"] = result.to_dict()
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except GoogleSheetError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
