"""Manual one-account, one-ad publish test with dry-run as the default."""

import argparse
import hashlib
import json

from app.browser import BrowserFactory
from app.logging_config import configure_logging
from app.models import Advertisement
from app.services import AccountService, PublishService
from app.storage import AccountStore, ProcessedRowStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill one Haraj service-ad form for a V2 account.")
    parser.add_argument("--account-id", required=True, help="Stable V2 account id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--image", default="", help="Currently unsupported; a non-empty value fails safely")
    parser.add_argument("--source-key", help="Stable source-row key; generated from content when omitted")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--manual-timeout", type=float, default=300)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually click Publish. Without this flag the command stops after filling the form.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    canonical = "\0".join((args.account_id, args.title, args.body, args.phone, args.image))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    source_key = args.source_key or f"manual-{content_hash}"
    advertisement = Advertisement(
        id=f"manual-{content_hash[:24]}",
        account_id=args.account_id,
        title=args.title,
        body=args.body,
        phone=args.phone,
        image=args.image,
        source_key=source_key,
    )
    service = PublishService(
        AccountService(AccountStore()),
        BrowserFactory(),
        ProcessedRowStore(),
    )
    result = service.publish_ad(
        args.account_id,
        advertisement,
        headless=args.headless,
        dry_run=not args.execute,
        manual_verification_timeout=args.manual_timeout,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
