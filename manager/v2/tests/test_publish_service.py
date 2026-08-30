from pathlib import Path
from unittest.mock import Mock

from app.models import AccountStatus, Advertisement, JobStatus
from app.services import AccountService, PublishService
from app.storage import AccountStore, ProcessedRowStore


def make_account_service(tmp_path: Path) -> AccountService:
    ids = iter(("account-1", "account-2", "account-3"))
    return AccountService(
        AccountStore(tmp_path / "accounts.enc", tmp_path / ".secret.key"),
        id_factory=lambda: next(ids),
        timestamp_factory=lambda: "2026-08-30T16:00:00+03:00",
    )


def make_ad(account_id: str, ad_id: str = "ad-1", source_key: str = "row-key") -> Advertisement:
    return Advertisement(
        ad_id,
        account_id,
        "عنوان",
        "نص",
        phone="0500000000",
        source_key=source_key,
    )


def make_service(
    tmp_path: Path,
    accounts: AccountService,
    browser_factory: Mock,
    page: Mock,
) -> tuple[PublishService, ProcessedRowStore]:
    processed = ProcessedRowStore(tmp_path / "published_rows.json")
    service = PublishService(
        accounts,
        browser_factory,
        processed,
        page_factory=Mock(return_value=page),
        errors_dir=tmp_path / "errors",
        filename_timestamp=lambda: "20260830_160000_000000",
    )
    return service, processed


def test_publish_service_defaults_to_dry_run_and_does_not_mark_row(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    account = accounts.add_account(name="حساب", username="0500000000", password="secret")
    driver = Mock()
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.publish_ad.return_value = False
    service, processed = make_service(tmp_path, accounts, browser_factory, page)

    result = service.publish_ad(account.id, make_ad(account.id))

    assert result.status is JobStatus.DRY_RUN
    assert result.dry_run == 1
    page.publish_ad.assert_called_once_with(make_ad(account.id), dry_run=True)
    assert processed.list_keys() == set()
    assert accounts.get_account(account.id).last_status is AccountStatus.IDLE
    driver.quit.assert_called_once_with()


def test_live_success_marks_row_and_prevents_republishing(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    account = accounts.add_account(name="حساب", username="0500000000", password="secret")
    driver = Mock()
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.publish_ad.return_value = True
    service, processed = make_service(tmp_path, accounts, browser_factory, page)
    advertisement = make_ad(account.id)

    first = service.publish_ad(account.id, advertisement, dry_run=False)
    second = service.publish_ad(account.id, advertisement, dry_run=False)

    assert first.status is JobStatus.SUCCESS
    assert processed.is_processed("row-key") is True
    assert second.status is JobStatus.SKIPPED
    assert second.skipped == 1
    assert browser_factory.create.call_count == 1


def test_publish_continues_after_phone_failure_and_captures_screenshot(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    account = accounts.add_account(name="حساب", username="0500000000", password="secret")
    driver = Mock()
    driver.save_screenshot.return_value = True
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.publish_ad.side_effect = [RuntimeError("phone mismatch"), True]
    service, processed = make_service(tmp_path, accounts, browser_factory, page)
    advertisements = [make_ad(account.id, "ad-1", "row-1"), make_ad(account.id, "ad-2", "row-2")]

    result = service.publish_account(account.id, advertisements, dry_run=False)

    assert result.status is JobStatus.PARTIAL_SUCCESS
    assert result.failed == 1
    assert result.succeeded == 1
    assert result.advertisements[0].screenshot_path.endswith(".png")
    assert processed.is_processed("row-1") is False
    assert processed.is_processed("row-2") is True
    assert page.publish_ad.call_count == 2


def test_publish_all_continues_after_account_failure_and_skips_paused(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    failed = accounts.add_account(name="فاشل", username="0500000000", password="secret")
    paused = accounts.add_account(name="متوقف", username="0500000001", password="secret")
    accounts.pause_account(paused.id)
    successful = accounts.add_account(name="ناجح", username="0500000002", password="secret")
    good_driver = Mock()
    browser_factory = Mock()
    browser_factory.create.side_effect = [RuntimeError("browser failed"), good_driver]
    page = Mock()
    page.publish_ad.return_value = True
    service, _processed = make_service(tmp_path, accounts, browser_factory, page)

    batch = service.publish_all(
        [
            make_ad(failed.id, "ad-1", "row-1"),
            make_ad(paused.id, "ad-2", "row-2"),
            make_ad(successful.id, "ad-3", "row-3"),
        ],
        dry_run=False,
    )

    assert [result.status for result in batch.accounts] == [
        JobStatus.FAILED,
        JobStatus.SKIPPED,
        JobStatus.SUCCESS,
    ]
    assert browser_factory.create.call_count == 2
    good_driver.quit.assert_called_once_with()
