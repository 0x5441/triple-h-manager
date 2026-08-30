"""CLI for safely testing existing-ad updates for one V2 account."""

import argparse
import json

from app.browser import BrowserFactory
from app.logging_config import configure_logging
from app.services import AccountService, UpdateService
from app.storage import AccountStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test existing-ad updates for one V2 account.")
    parser.add_argument("--account-id", required=True, help="Stable V2 account id")
    parser.add_argument("--url", help="Test only this Haraj ad URL; otherwise use all saved account ads")
    parser.add_argument("--headless", action="store_true", help="Run Chrome without a visible window")
    parser.add_argument("--manual-timeout", type=float, default=300)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually click Update. Without this flag the command is a safe dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    service = UpdateService(AccountService(AccountStore()), BrowserFactory())
    options = {
        "headless": args.headless,
        "dry_run": not args.execute,
        "manual_verification_timeout": args.manual_timeout,
    }
    if args.url:
        result = service.update_ad(args.account_id, args.url, **options)
    else:
        result = service.update_account(args.account_id, **options)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
