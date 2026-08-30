from pathlib import Path
from unittest.mock import Mock

from app.models import AccountStatus, JobStatus
from app.services import AccountService, UpdateService
from app.storage import AccountStore


def make_account_service(tmp_path: Path) -> AccountService:
    ids = iter(("account-1", "account-2", "account-3", "account-4"))
    return AccountService(
        AccountStore(tmp_path / "accounts.enc", tmp_path / ".secret.key"),
        id_factory=lambda: next(ids),
        timestamp_factory=lambda: "2026-08-30T15:00:00+03:00",
    )


def make_update_service(
    tmp_path: Path,
    accounts: AccountService,
    browser_factory: Mock,
    page: Mock,
) -> UpdateService:
    return UpdateService(
        accounts,
        browser_factory,
        page_factory=Mock(return_value=page),
        errors_dir=tmp_path / "errors",
        filename_timestamp=lambda: "20260830_150000_000000",
    )


def test_update_one_ad_uses_saved_session_profile_and_records_success(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    account = accounts.add_account(
        name="حساب",
        username="0500000000",
        password="secret",
        ads=["https://haraj.com.sa/saved"],
    )
    driver = Mock()
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.update_ad.return_value = True
    service = make_update_service(tmp_path, accounts, browser_factory, page)

    result = service.update_ad(account.id, "https://haraj.com.sa/one")

    assert result.status is JobStatus.SUCCESS
    assert result.succeeded == 1
    page.ensure_logged_in.assert_called_once()
    page.update_ad.assert_called_once_with("https://haraj.com.sa/one", dry_run=False)
    driver.quit.assert_called_once_with()
    stored = accounts.get_account(account.id)
    assert stored.last_status is AccountStatus.SUCCESS
    assert stored.last_run_at == "2026-08-30T15:00:00+03:00"


def test_update_account_continues_after_ad_failure_and_takes_screenshot(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    urls = [
        "https://haraj.com.sa/one",
        "https://haraj.com.sa/two",
        "https://haraj.com.sa/three",
    ]
    account = accounts.add_account(
        name="حساب",
        username="0500000000",
        password="secret",
        ads=urls,
    )
    driver = Mock()
    driver.save_screenshot.return_value = True
    browser_factory = Mock()
    browser_factory.create.return_value = driver
    page = Mock()
    page.update_ad.side_effect = [True, RuntimeError("second failed"), True]
    service = make_update_service(tmp_path, accounts, browser_factory, page)

    result = service.update_account(account.id)

    assert result.status is JobStatus.PARTIAL_SUCCESS
    assert result.succeeded == 2
    assert result.failed == 1
    assert page.update_ad.call_count == 3
    assert result.ads[1].screenshot_path.endswith(".png")
    driver.save_screenshot.assert_called_once()
    assert accounts.get_account(account.id).last_status is AccountStatus.PARTIAL_SUCCESS


def test_update_all_skips_paused_and_continues_after_account_failure(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    failed = accounts.add_account(
        name="فاشل",
        username="0500000000",
        password="secret",
        ads=["https://haraj.com.sa/fail"],
    )
    paused = accounts.add_account(
        name="متوقف",
        username="0500000001",
        password="secret",
        ads=["https://haraj.com.sa/paused"],
    )
    accounts.pause_account(paused.id)
    successful = accounts.add_account(
        name="ناجح",
        username="0500000002",
        password="secret",
        ads=["https://haraj.com.sa/success"],
    )
    good_driver = Mock()
    browser_factory = Mock()
    browser_factory.create.side_effect = [RuntimeError("browser failed"), good_driver]
    page = Mock()
    page.update_ad.return_value = True
    service = make_update_service(tmp_path, accounts, browser_factory, page)

    batch = service.update_all_accounts()

    assert [item.account_id for item in batch.accounts] == [failed.id, paused.id, successful.id]
    assert [item.status for item in batch.accounts] == [
        JobStatus.FAILED,
        JobStatus.SKIPPED,
        JobStatus.SUCCESS,
    ]
    assert batch.failed == 1
    assert batch.succeeded == 1
    assert batch.skipped_accounts == 1
    assert browser_factory.create.call_count == 2
    good_driver.quit.assert_called_once_with()


def test_dry_run_checks_update_without_claiming_account_success(tmp_path: Path) -> None:
    accounts = make_account_service(tmp_path)
    account = accounts.add_account(
        name="حساب",
        username="0500000000",
        password="secret",
        ads=["https://haraj.com.sa/one"],
    )
    browser_factory = Mock()
    browser_factory.create.return_value = Mock()
    page = Mock()
    page.update_ad.return_value = False
    service = make_update_service(tmp_path, accounts, browser_factory, page)

    result = service.update_account(account.id, dry_run=True)

    assert result.status is JobStatus.DRY_RUN
    assert result.dry_run == 1
    assert accounts.get_account(account.id).last_status is AccountStatus.IDLE
