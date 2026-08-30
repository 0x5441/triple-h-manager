import threading
import time

from app.services import JobEventType, JobRunner, TaskOutcome


def wait_until_finished(runner: JobRunner) -> None:
    deadline = time.monotonic() + 2
    while runner.running and time.monotonic() < deadline:
        time.sleep(0.005)
    assert runner.running is False


def test_job_runner_emits_progress_and_isolates_item_failure() -> None:
    runner = JobRunner()
    entered = threading.Event()
    release = threading.Event()

    def worker(item: int) -> TaskOutcome:
        if item == 1:
            entered.set()
            release.wait(timeout=1)
        if item == 2:
            raise RuntimeError("فشل العنصر الثاني")
        return TaskOutcome(True, payload=item * 10, message=f"نجح {item}")

    assert runner.start("اختبار", [1, 2, 3], worker) is True
    assert entered.wait(timeout=1)
    assert runner.start("متعارض", [4], worker) is False
    release.set()
    wait_until_finished(runner)
    events = runner.poll_events()
    completed = next(event for event in events if event.type is JobEventType.COMPLETED)
    item_results = [event for event in events if event.type is JobEventType.ITEM_RESULT]

    assert len(item_results) == 3
    assert completed.progress is not None
    assert completed.progress.succeeded == 2
    assert completed.progress.failed == 1
    assert completed.progress.remaining == 0


def test_job_runner_cancels_between_items_not_during_current_step() -> None:
    runner = JobRunner()
    entered = threading.Event()
    release = threading.Event()
    visited: list[int] = []

    def worker(item: int) -> TaskOutcome:
        visited.append(item)
        entered.set()
        release.wait(timeout=1)
        return TaskOutcome(True, payload=item)

    assert runner.start("إيقاف آمن", [1, 2, 3], worker) is True
    assert entered.wait(timeout=1)
    assert runner.cancel() is True
    release.set()
    wait_until_finished(runner)
    events = runner.poll_events()
    terminal = next(event for event in events if event.type is JobEventType.CANCELLED)

    assert visited == [1]
    assert terminal.progress is not None
    assert terminal.progress.completed == 1
    assert terminal.progress.remaining == 2
