"""Orchestrate safe, deduplicated advertisement publishing."""

import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from app.browser import BrowserFactory, HarajPage
from app.config import ERRORS_DIR
from app.models import (
    Account,
    AccountPublishResult,
    AccountStatus,
    AdPublishResult,
    Advertisement,
    JobStatus,
    PublishBatchResult,
)
from app.services.account_service import AccountService
from app.storage import ProcessedRowStore


def _filename_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")


class PublishService:
    """Publish sequentially per account and keep failures isolated."""

    def __init__(
        self,
        account_service: AccountService,
        browser_factory: BrowserFactory,
        processed_store: ProcessedRowStore,
        *,
        page_factory: Any = HarajPage,
        errors_dir: Path | str = ERRORS_DIR,
        filename_timestamp: Callable[[], str] = _filename_timestamp,
        logger: logging.Logger | None = None,
    ) -> None:
        self._accounts = account_service
        self._browser_factory = browser_factory
        self._processed = processed_store
        self._page_factory = page_factory
        self._errors_dir = Path(errors_dir)
        self._filename_timestamp = filename_timestamp
        self.log = logger or logging.getLogger(__name__)

    def publish_ad(
        self,
        account_id: str,
        advertisement: Advertisement,
        *,
        headless: bool = False,
        dry_run: bool = True,
        manual_verification_timeout: float = 300,
    ) -> AccountPublishResult:
        account = self._accounts.get_account(account_id)
        return self._run_account(
            account,
            [advertisement],
            headless=headless,
            dry_run=dry_run,
            manual_verification_timeout=manual_verification_timeout,
        )

    def publish_account(
        self,
        account_id: str,
        advertisements: Sequence[Advertisement],
        *,
        headless: bool = False,
        dry_run: bool = True,
        manual_verification_timeout: float = 300,
    ) -> AccountPublishResult:
        account = self._accounts.get_account(account_id)
        return self._run_account(
            account,
            list(advertisements),
            headless=headless,
            dry_run=dry_run,
            manual_verification_timeout=manual_verification_timeout,
        )

    def publish_all(
        self,
        advertisements: Sequence[Advertisement],
        *,
        headless: bool = False,
        dry_run: bool = True,
        manual_verification_timeout: float = 300,
    ) -> PublishBatchResult:
        grouped: dict[str, list[Advertisement]] = defaultdict(list)
        for advertisement in advertisements:
            grouped[advertisement.account_id].append(advertisement)

        batch = PublishBatchResult()
        for account_id, account_ads in grouped.items():
            try:
                account = self._accounts.get_account(account_id)
                result = self._run_account(
                    account,
                    account_ads,
                    headless=headless,
                    dry_run=dry_run,
                    manual_verification_timeout=manual_verification_timeout,
                )
            except Exception as exc:
                self.log.exception("Unexpected publish failure for account %s", account_id)
                result = AccountPublishResult(
                    account_id,
                    JobStatus.FAILED,
                    [
                        AdPublishResult(
                            account_id,
                            advertisement.id,
                            advertisement.source_key,
                            JobStatus.FAILED,
                            str(exc),
                        )
                        for advertisement in account_ads
                    ],
                    str(exc),
                )
            batch.accounts.append(result)
        return batch

    def _run_account(
        self,
        account: Account,
        advertisements: list[Advertisement],
        *,
        headless: bool,
        dry_run: bool,
        manual_verification_timeout: float,
    ) -> AccountPublishResult:
        if account.paused:
            self.log.info("Skipping paused account %s", account.id)
            return AccountPublishResult(
                account.id,
                JobStatus.SKIPPED,
                [
                    AdPublishResult(
                        account.id,
                        advertisement.id,
                        advertisement.source_key,
                        JobStatus.SKIPPED,
                        "Account is paused",
                    )
                    for advertisement in advertisements
                ],
                "Account is paused",
            )

        results: list[AdPublishResult] = []
        pending: list[Advertisement] = []
        processed_keys = self._processed.list_keys()
        seen_keys = set(processed_keys)
        for advertisement in advertisements:
            if advertisement.account_id != account.id:
                results.append(
                    AdPublishResult(
                        account.id,
                        advertisement.id,
                        advertisement.source_key,
                        JobStatus.FAILED,
                        "Advertisement account_id does not match the selected account",
                    )
                )
            elif advertisement.source_key and advertisement.source_key in seen_keys:
                results.append(
                    AdPublishResult(
                        account.id,
                        advertisement.id,
                        advertisement.source_key,
                        JobStatus.SKIPPED,
                        "Advertisement source row was already processed",
                    )
                )
            else:
                pending.append(advertisement)
                if advertisement.source_key:
                    seen_keys.add(advertisement.source_key)

        if not pending:
            status = JobStatus.FAILED if any(item.status is JobStatus.FAILED for item in results) else JobStatus.SKIPPED
            result = AccountPublishResult(account.id, status, results)
            if status is JobStatus.FAILED:
                self._record_status(result, AccountStatus.FAILED)
            return result

        driver = None
        try:
            driver = self._browser_factory.create(account.id, headless=headless)
            page = self._page_factory(driver, headless=headless)
            page.ensure_logged_in(
                account,
                manual_verification_timeout=manual_verification_timeout,
            )
            for index, advertisement in enumerate(pending, start=1):
                try:
                    executed = page.publish_ad(advertisement, dry_run=dry_run)
                    if not executed:
                        results.append(
                            AdPublishResult(
                                account.id,
                                advertisement.id,
                                advertisement.source_key,
                                JobStatus.DRY_RUN,
                                "Dry-run filled the form without clicking publish",
                            )
                        )
                        continue
                    if advertisement.source_key:
                        self._processed.mark_processed(advertisement.source_key)
                    results.append(
                        AdPublishResult(
                            account.id,
                            advertisement.id,
                            advertisement.source_key,
                            JobStatus.SUCCESS,
                            "Advertisement publish was verified",
                        )
                    )
                    self.log.info("Published advertisement %s for account %s", advertisement.id, account.id)
                except Exception as exc:
                    screenshot = self._capture_screenshot(driver, account.id, index)
                    results.append(
                        AdPublishResult(
                            account.id,
                            advertisement.id,
                            advertisement.source_key,
                            JobStatus.FAILED,
                            str(exc) or "Advertisement publish failed",
                            screenshot,
                        )
                    )
                    self.log.error(
                        "Publish failed for account %s, advertisement %s: %s",
                        account.id,
                        advertisement.id,
                        exc,
                    )
        except Exception as exc:
            screenshot = self._capture_screenshot(driver, account.id, 0) if driver is not None else ""
            results.extend(
                AdPublishResult(
                    account.id,
                    advertisement.id,
                    advertisement.source_key,
                    JobStatus.FAILED,
                    str(exc) or "Account browser or session failed",
                    screenshot,
                )
                for advertisement in pending
            )
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        job_status, account_status = self._summarize(results, dry_run=dry_run)
        result = AccountPublishResult(account.id, job_status, results)
        self._record_status(result, account_status)
        return result

    @staticmethod
    def _summarize(
        results: list[AdPublishResult],
        *,
        dry_run: bool,
    ) -> tuple[JobStatus, AccountStatus]:
        failed = sum(item.status is JobStatus.FAILED for item in results)
        completed = sum(item.status in {JobStatus.SUCCESS, JobStatus.DRY_RUN} for item in results)
        if failed and completed:
            return JobStatus.PARTIAL_SUCCESS, AccountStatus.PARTIAL_SUCCESS
        if failed:
            return JobStatus.FAILED, AccountStatus.FAILED
        if dry_run and completed:
            return JobStatus.DRY_RUN, AccountStatus.IDLE
        if completed:
            return JobStatus.SUCCESS, AccountStatus.SUCCESS
        return JobStatus.SKIPPED, AccountStatus.IDLE

    def _record_status(self, result: AccountPublishResult, status: AccountStatus) -> None:
        try:
            self._accounts.record_run(result.account_id, status)
        except Exception as exc:
            suffix = f"Account status could not be persisted: {exc}"
            result.message = f"{result.message}; {suffix}" if result.message else suffix
            self.log.error("Could not persist publish status for %s: %s", result.account_id, exc)

    def _capture_screenshot(self, driver: Any, account_id: str, index: int) -> str:
        safe_id = "".join(character for character in account_id if character.isalnum() or character in "-_")
        safe_id = safe_id or "account"
        self._errors_dir.mkdir(parents=True, exist_ok=True)
        path = self._errors_dir / f"publish_{safe_id}_{index}_{self._filename_timestamp()}.png"
        try:
            return str(path) if driver.save_screenshot(str(path)) else ""
        except Exception:
            return ""
