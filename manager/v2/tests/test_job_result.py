import pytest

from app.models import JobResult, JobStatus


def test_job_result_calculates_total_and_normalizes_messages() -> None:
    result = JobResult(
        status=JobStatus.PARTIAL_SUCCESS,
        succeeded=2,
        failed=1,
        skipped=1,
    )

    result.add_message("  اكتملت العملية جزئيًا  ")

    assert result.total == 4
    assert result.messages == ["اكتملت العملية جزئيًا"]


def test_job_result_rejects_negative_counters() -> None:
    with pytest.raises(ValueError, match="negative"):
        JobResult(failed=-1)

