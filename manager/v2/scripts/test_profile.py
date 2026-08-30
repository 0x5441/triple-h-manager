"""Manual, login-only validation of an isolated V2 Chrome profile."""

import argparse
from getpass import getpass

from app.browser import BrowserFactory
from app.logging_config import configure_logging
from app.models import Account
from app.services import ProfileService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or refresh a Haraj session without publishing or updating ads."
    )
    parser.add_argument("--account-id", required=True, help="Stable V2 account id used for the profile folder")
    parser.add_argument("--username", required=True, help="Haraj account number")
    parser.add_argument("--name", default="Manual profile test", help="Display name used only in memory")
    parser.add_argument("--headless", action="store_true", help="Run Chrome without a visible window")
    parser.add_argument("--manual-timeout", type=float, default=300, help="Seconds allowed for manual verification")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = getpass("Haraj password: ")
    if not password:
        print("Password must not be empty")
        return 2

    configure_logging()
    account = Account(
        id=args.account_id,
        name=args.name,
        username=args.username,
        password=password,
    )
    result = ProfileService(BrowserFactory()).test_profile(
        account,
        headless=args.headless,
        manual_verification_timeout=args.manual_timeout,
    )
    print(f"status={result.status.value}")
    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
