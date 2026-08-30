"""Orchestrate resilient existing-ad update jobs."""

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.browser import BrowserFactory, HarajPage
from app.config import ERRORS_DIR
from app.models import (
    Account,
    AccountStatus,
    AccountUpdateResult,
    AdUpdateResult,
    JobStatus,
    UpdateBatchResult,
)
from app.services.account_service import AccountService


def _filename_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")


class UpdateService:
    """Use one isolated browser per account and continue after individual failures."""

    def __init__(
        self,
        account_service: AccountService,
        browser_factory: BrowserFactory,
        *,
        page_factory: Any = HarajPage,
        errors_dir: Path | str = ERRORS_DIR,
        filename_timestamp: Callable[[], str] = _filename_timestamp,
        logger: logging.Logger | None = None,
    ) -> None:
        self._accounts = account_service
        self._browser_factory = browser_factory
        self._page_factory = page_factory
        self._errors_dir = Path(errors_dir)
        self._filename_timestamp = filename_timestamp
        self.log = logger or logging.getLogger(__name__)

    def update_ad(
        self,
        account_id: str,
        url: str,
        *,
        headless: bool = False,
        dry_run: bool = False,
        manual_verification_timeout: float = 300,
    ) -> AccountUpdateResult:
        account = self._accounts.get_account(account_id)
        return self._run_account(
            account,
            [url],
            headless=headless,
            dry_run=dry_run,
            manual_verification_timeout=manual_verification_timeout,
        )

    def update_account(
        self,
        account_id: str,
        *,
        headless: bool = False,
        dry_run: bool = False,
        manual_verification_timeout: float = 300,
    ) -> AccountUpdateResult:
        account = self._accounts.get_account(account_id)
        return self._run_account(
            account,
            list(account.ads),
            headless=headless,
            dry_run=dry_run,
            manual_verification_timeout=manual_verification_timeout,
        )

    def update_all_accounts(
        self,
        *,
        headless: bool = False,
        dry_run: bool = False,
        manual_verification_timeout: float = 300,
    ) -> UpdateBatchResult:
        batch = UpdateBatchResult()
        for account in self._accounts.list_accounts():
            try:
                result = self._run_account(
                    account,
                    list(account.ads),
                    headless=headless,
                    dry_run=dry_run,
                    manual_verification_timeout=manual_verification_timeout,
                )
            except Exception as exc:
                self.log.exception("Unexpected account update failure for %s", account.id)
                result = AccountUpdateResult(
                    account_id=account.id,
                    status=JobStatus.FAILED,
                    ads=[
                        AdUpdateResult(account.id, url, JobStatus.FAILED, str(exc))
                        for url in account.ads
                    ],
                    message=str(exc),
                )
                self._record_status(result, AccountStatus.FAILED)
            batch.accounts.append(result)
        return batch

    def _run_account(
        self,
        account: Account,
        urls: list[str],
        *,
        headless: bool,
        dry_run: bool,
        manual_verification_timeout: float,
    ) -> AccountUpdateResult:
        if account.paused:
            self.log.info("Skipping paused account %s", account.id)
            return AccountUpdateResult(
                account_id=account.id,
                status=JobStatus.SKIPPED,
                message="Account is paused",
            )
        if not urls:
            result = AccountUpdateResult(
                account_id=account.id,
                status=JobStatus.SKIPPED,
                message="Account has no advertisement URLs",
            )
            self._record_status(result, AccountStatus.IDLE)
            return result

        driver = None
        ad_results: list[AdUpdateResult] = []
        try:
            driver = self._browser_factory.create(account.id, headless=headless)
            page = self._page_factory(driver, headless=headless)
            page.ensure_logged_in(
                account,
                manual_verification_timeout=manual_verification_timeout,
            )

            for index, url in enumerate(urls, start=1):
                try:
                    executed = page.update_ad(url, dry_run=dry_run)
                    status = JobStatus.SUCCESS if executed else JobStatus.DRY_RUN
                    message = "Advertisement update verified" if executed else "Dry-run verified update availability"
                    ad_results.append(AdUpdateResult(account.id, url, status, message))
                    self.log.info("%s for account %s: %s", status.value, account.id, url)
                except Exception as exc:
                    screenshot = self._capture_screenshot(driver, account.id, index)
                    ad_results.append(
                        AdUpdateResult(
                            account.id,
                            url,
                            JobStatus.FAILED,
                            str(exc) or "Advertisement update failed",
                            screenshot,
                        )
                    )
                    self.log.error("Update failed for account %s: %s — %s", account.id, url, exc)
        except Exception as exc:
            screenshot = self._capture_screenshot(driver, account.id, 0) if driver is not None else ""
            for url in urls:
                ad_results.append(
                    AdUpdateResult(
                        account.id,
                        url,
                        JobStatus.FAILED,
                        str(exc) or "Account browser or session failed",
                        screenshot,
                    )
                )
            self.log.error("Account update failed before ads for %s: %s", account.id, exc)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        account_status, stored_status = self._summarize(ad_results, dry_run=dry_run)
        result = AccountUpdateResult(account.id, account_status, ad_results)
        self._record_status(result, stored_status)
        return result

    @staticmethod
    def _summarize(
        results: list[AdUpdateResult],
        *,
        dry_run: bool,
    ) -> tuple[JobStatus, AccountStatus]:
        failures = sum(item.status is JobStatus.FAILED for item in results)
        successes = len(results) - failures
        if failures and successes:
            return JobStatus.PARTIAL_SUCCESS, AccountStatus.PARTIAL_SUCCESS
        if failures:
            return JobStatus.FAILED, AccountStatus.FAILED
        if dry_run:
            return JobStatus.DRY_RUN, AccountStatus.IDLE
        return JobStatus.SUCCESS, AccountStatus.SUCCESS

    def _record_status(self, result: AccountUpdateResult, status: AccountStatus) -> None:
        try:
            self._accounts.record_run(result.account_id, status)
        except Exception as exc:
            suffix = f"Account status could not be persisted: {exc}"
            result.message = f"{result.message}; {suffix}" if result.message else suffix
            self.log.error("Could not persist update status for %s: %s", result.account_id, exc)

    def _capture_screenshot(self, driver: Any, account_id: str, index: int) -> str:
        safe_id = "".join(character for character in account_id if character.isalnum() or character in "-_")
        safe_id = safe_id or "account"
        self._errors_dir.mkdir(parents=True, exist_ok=True)
        path = self._errors_dir / f"update_{safe_id}_{index}_{self._filename_timestamp()}.png"
        try:
            return str(path) if driver.save_screenshot(str(path)) else ""
        except Exception:
            return ""
