from locust import HttpUser, between, task

JOB = {"job_type": "fibonacci", "payload": {"n": 32}}


class AsyncUser(HttpUser):
    """Submits the job to the queue and returns immediately."""

    wait_time = between(0.5, 1.5)

    @task
    def submit_job(self):
        self.client.post("/jobs", json=JOB, name="POST /jobs (queued)")


class SyncUser(HttpUser):
    """Baseline: the API does the work inside the request."""

    wait_time = between(0.5, 1.5)

    @task
    def run_inline(self):
        self.client.post("/benchmark/sync", json=JOB, name="POST /benchmark/sync (inline)")
