"""Job execution result model."""

from dataclasses import dataclass, field

from app.models.enums import JobStatus


@dataclass(slots=True)
class JobResult:
    status: JobStatus = JobStatus.PENDING
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    messages: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if min(self.succeeded, self.failed, self.skipped) < 0:
            raise ValueError("Job result counters must not be negative")

    @property
    def total(self) -> int:
        return self.succeeded + self.failed + self.skipped

    def add_message(self, message: str) -> None:
        normalized = message.strip()
        if normalized:
            self.messages.append(normalized)

