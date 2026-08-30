"""Structured results for advertisement publishing jobs."""

from dataclasses import dataclass, field

from app.models.enums import JobStatus


@dataclass(frozen=True, slots=True)
class AdPublishResult:
    account_id: str
    advertisement_id: str
    source_key: str
    status: JobStatus
    message: str
    screenshot_path: str = ""

    @property
    def success(self) -> bool:
        return self.status in {JobStatus.SUCCESS, JobStatus.DRY_RUN}

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "account_id": self.account_id,
            "advertisement_id": self.advertisement_id,
            "source_key": self.source_key,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "screenshot_path": self.screenshot_path,
        }


@dataclass(slots=True)
class AccountPublishResult:
    account_id: str
    status: JobStatus
    advertisements: list[AdPublishResult] = field(default_factory=list)
    message: str = ""

    @property
    def succeeded(self) -> int:
        return sum(item.status is JobStatus.SUCCESS for item in self.advertisements)

    @property
    def failed(self) -> int:
        return sum(item.status is JobStatus.FAILED for item in self.advertisements)

    @property
    def dry_run(self) -> int:
        return sum(item.status is JobStatus.DRY_RUN for item in self.advertisements)

    @property
    def skipped(self) -> int:
        return sum(item.status is JobStatus.SKIPPED for item in self.advertisements)

    def to_dict(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "status": self.status.value,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "skipped": self.skipped,
            "message": self.message,
            "advertisements": [item.to_dict() for item in self.advertisements],
        }


@dataclass(slots=True)
class PublishBatchResult:
    accounts: list[AccountPublishResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(account.succeeded for account in self.accounts)

    @property
    def failed(self) -> int:
        return sum(account.failed for account in self.accounts)

    def to_dict(self) -> dict[str, object]:
        return {
            "succeeded": self.succeeded,
            "failed": self.failed,
            "accounts": [account.to_dict() for account in self.accounts],
        }
