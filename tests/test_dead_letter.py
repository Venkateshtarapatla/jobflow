from app.models import Job, JobStatus


def add_job(db, status, error=None):
    job = Job(job_type="flaky", payload={}, status=status, error=error, retry_count=3)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def test_lists_only_dead_jobs(client, db):
    dead_id = add_job(db, JobStatus.DEAD, "RuntimeError: boom")
    add_job(db, JobStatus.SUCCESS)
    response = client.get("/dead-letter/jobs")
    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [dead_id]


def test_retry_requeues_dead_job(client, db, delay_mock):
    job_id = add_job(db, JobStatus.DEAD, "RuntimeError: boom")
    response = client.post(f"/dead-letter/jobs/{job_id}/retry")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["retry_count"] == 0
    assert body["error"] is None
    delay_mock.assert_called_once_with(job_id)


def test_retry_rejects_non_dead_job(client, db, delay_mock):
    job_id = add_job(db, JobStatus.SUCCESS)
    assert client.post(f"/dead-letter/jobs/{job_id}/retry").status_code == 404
    delay_mock.assert_not_called()


def test_retry_missing_job_returns_404(client):
    assert client.post("/dead-letter/jobs/9999/retry").status_code == 404
