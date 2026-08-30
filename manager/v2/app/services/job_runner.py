"""Single-worker job execution with Queue events and cooperative cancellation."""

import queue
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class JobEventType(str, Enum):
    STARTED = "started"
    ITEM_STARTED = "item_started"
    ITEM_RESULT = "item_result"
    PROGRESS = "progress"
    LOG = "log"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    success: bool
    payload: Any = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class JobProgress:
    total: int
    completed: int
    succeeded: int
    failed: int

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.completed)

    @property
    def percent(self) -> float:
        return 100.0 if self.total == 0 else (self.completed / self.total) * 100


@dataclass(frozen=True, slots=True)
class JobEvent:
    type: JobEventType
    job_name: str
    message: str = ""
    item: Any = None
    payload: Any = None
    progress: JobProgress | None = None


class JobRunner:
    """Run one job at a time; worker threads only emit Queue events."""

    def __init__(self) -> None:
        self.events: queue.Queue[JobEvent] = queue.Queue()
        self._cancel = threading.Event()
        self._state_lock = threading.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._running

    def start(
        self,
        job_name: str,
        items: Sequence[Any],
        worker: Callable[[Any], TaskOutcome],
    ) -> bool:
        with self._state_lock:
            if self._running:
                return False
            self._running = True
            self._cancel.clear()
        snapshot = list(items)
        thread = threading.Thread(
            target=self._run,
            args=(job_name, snapshot, worker),
            daemon=True,
            name=f"v2-job-{job_name}",
        )
        thread.start()
        return True

    def cancel(self) -> bool:
        if not self.running:
            return False
        self._cancel.set()
        return True

    def poll_events(self) -> list[JobEvent]:
        found: list[JobEvent] = []
        while True:
            try:
                found.append(self.events.get_nowait())
            except queue.Empty:
                return found

    def emit_log(self, job_name: str, message: str) -> None:
        self.events.put(JobEvent(JobEventType.LOG, job_name, message=message))

    def _run(self, job_name: str, items: list[Any], worker: Callable[[Any], TaskOutcome]) -> None:
        total = len(items)
        completed = succeeded = failed = 0
        self.events.put(
            JobEvent(
                JobEventType.STARTED,
                job_name,
                message=f"بدأت العملية: {job_name}",
                progress=JobProgress(total, completed, succeeded, failed),
            )
        )
        try:
            for item in items:
                if self._cancel.is_set():
                    break
                self.events.put(JobEvent(JobEventType.ITEM_STARTED, job_name, item=item))
                try:
                    outcome = worker(item)
                except Exception as exc:
                    detail = str(exc).strip()
                    outcome = TaskOutcome(
                        False,
                        message=f"فشلت الخطوة: {detail}" if detail else "فشلت الخطوة",
                    )
                completed += 1
                succeeded += int(outcome.success)
                failed += int(not outcome.success)
                progress = JobProgress(total, completed, succeeded, failed)
                self.events.put(
                    JobEvent(
                        JobEventType.ITEM_RESULT,
                        job_name,
                        message=outcome.message,
                        item=item,
                        payload=outcome.payload,
                        progress=progress,
                    )
                )
                self.events.put(JobEvent(JobEventType.PROGRESS, job_name, progress=progress))

            progress = JobProgress(total, completed, succeeded, failed)
            event_type = JobEventType.CANCELLED if self._cancel.is_set() else JobEventType.COMPLETED
            message = "تم إيقاف العملية بأمان" if self._cancel.is_set() else "اكتملت العملية"
            self.events.put(JobEvent(event_type, job_name, message=message, progress=progress))
        finally:
            with self._state_lock:
                self._running = False
