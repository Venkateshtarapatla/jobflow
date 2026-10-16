from unittest.mock import patch

import pytest
from celery.exceptions import Retry

from app.models import Job, JobStatus
from app.tasks.handlers import HANDLERS
from app.worker import process_job


def make_job(db, job_type="fibonacci", payload=None, status=JobStatus.QUEUED):
    job = Job(job_type=job_type, payload=payload or {}, status=status)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def run_task(job_id, retries=0):
    process_job.push_request(retries=retries)
    try:
        return process_job.run(job_id)
    finally:
        process_job.pop_request()


def reload(db, job_id):
    db.expire_all()
    return db.get(Job, job_id)


def boom(payload):
    raise RuntimeError("boom")


def test_success_path(db):
    job_id = make_job(db, "fibonacci", {"n": 10})
    run_task(job_id)
    job = reload(db, job_id)
    assert job.status == JobStatus.SUCCESS
    assert job.result == {"n": 10, "value": 55}
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.error is None


@pytest.mark.parametrize(
    "attempt, expected_countdown, expected_retry_count",
    [(0, 2, 1), (1, 4, 2), (2, 8, 3)],
)
def test_failure_schedules_retry_with_exponential_backoff(
    db, monkeypatch, attempt, expected_countdown, expected_retry_count
):
    monkeypatch.setitem(HANDLERS, "flaky", boom)
    job_id = make_job(db, "flaky")
    with patch.object(process_job, "retry", side_effect=Retry()) as retry_mock:
        with pytest.raises(Retry):
            run_task(job_id, retries=attempt)
    job = reload(db, job_id)
    assert job.status == JobStatus.RETRYING
    assert job.retry_count == expected_retry_count
    assert job.error == "RuntimeError: boom"
    assert retry_mock.call_args.kwargs["countdown"] == expected_countdown


def test_job_goes_to_dead_letter_after_max_retries(db, monkeypatch):
    monkeypatch.setitem(HANDLERS, "flaky", boom)
    job_id = make_job(db, "flaky")
    with patch.object(process_job, "retry") as retry_mock:
        run_task(job_id, retries=3)
    job = reload(db, job_id)
    assert job.status == JobStatus.DEAD
    assert job.error == "RuntimeError: boom"
    assert job.completed_at is not None
    retry_mock.assert_not_called()


def test_finished_job_is_not_run_again(db, monkeypatch):
    monkeypatch.setitem(HANDLERS, "flaky", boom)
    job_id = make_job(db, "flaky", status=JobStatus.SUCCESS)
    run_task(job_id)
    assert reload(db, job_id).status == JobStatus.SUCCESS


def test_missing_job_is_ignored():
    assert run_task(9999) is None
