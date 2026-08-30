"""Structured results for existing-ad update jobs."""

from dataclasses import dataclass, field

from app.models.enums import JobStatus


@dataclass(frozen=True, slots=True)
class AdUpdateResult:
    account_id: str
    url: str
    status: JobStatus
    message: str
    screenshot_path: str = ""

    @property
    def success(self) -> bool:
        return self.status in {JobStatus.SUCCESS, JobStatus.DRY_RUN}

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "account_id": self.account_id,
            "url": self.url,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "screenshot_path": self.screenshot_path,
        }


@dataclass(slots=True)
class AccountUpdateResult:
    account_id: str
    status: JobStatus
    ads: list[AdUpdateResult] = field(default_factory=list)
    message: str = ""

    @property
    def succeeded(self) -> int:
        return sum(result.status is JobStatus.SUCCESS for result in self.ads)

    @property
    def failed(self) -> int:
        return sum(result.status is JobStatus.FAILED for result in self.ads)

    @property
    def dry_run(self) -> int:
        return sum(result.status is JobStatus.DRY_RUN for result in self.ads)

    def to_dict(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "status": self.status.value,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "message": self.message,
            "ads": [result.to_dict() for result in self.ads],
        }


@dataclass(slots=True)
class UpdateBatchResult:
    accounts: list[AccountUpdateResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(account.succeeded for account in self.accounts)

    @property
    def failed(self) -> int:
        return sum(account.failed for account in self.accounts)

    @property
    def skipped_accounts(self) -> int:
        return sum(account.status is JobStatus.SKIPPED for account in self.accounts)

    def to_dict(self) -> dict[str, object]:
        return {
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped_accounts": self.skipped_accounts,
            "accounts": [result.to_dict() for result in self.accounts],
        }
