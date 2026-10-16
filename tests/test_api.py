from app.models import Job, JobStatus


def create(client, job_type="fibonacci", payload=None):
    return client.post("/jobs", json={"job_type": job_type, "payload": payload or {}})


def test_create_job_queues_and_enqueues(client, delay_mock):
    response = create(client, "fibonacci", {"n": 10})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["payload"] == {"n": 10}
    delay_mock.assert_called_once_with(body["id"])


def test_create_job_rejects_unknown_type(client, delay_mock):
    response = create(client, "banana")
    assert response.status_code == 422
    delay_mock.assert_not_called()


def test_get_job(client, delay_mock):
    job_id = create(client).json()["id"]
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["id"] == job_id


def test_get_missing_job_returns_404(client):
    assert client.get("/jobs/9999").status_code == 404


def test_list_jobs_and_status_filter(client, delay_mock):
    create(client)
    create(client)
    assert len(client.get("/jobs").json()) == 2
    assert len(client.get("/jobs?status=QUEUED").json()) == 2
    assert client.get("/jobs?status=SUCCESS").json() == []


def test_list_jobs_respects_limit(client, delay_mock):
    for _ in range(3):
        create(client)
    assert len(client.get("/jobs?limit=2").json()) == 2


def test_delete_job(client, delay_mock):
    job_id = create(client).json()["id"]
    assert client.delete(f"/jobs/{job_id}").status_code == 204
    assert client.get(f"/jobs/{job_id}").status_code == 404


def test_delete_missing_job_returns_404(client):
    assert client.delete("/jobs/9999").status_code == 404


def test_cannot_delete_running_job(client, db, delay_mock):
    job_id = create(client).json()["id"]
    job = db.get(Job, job_id)
    job.status = JobStatus.RUNNING
    db.commit()
    assert client.delete(f"/jobs/{job_id}").status_code == 409
