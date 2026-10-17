![CI](https://github.com/Venkateshtarapatla/jobflow/actions/workflows/ci.yml/badge.svg)

# JobFlow: Distributed Job Processing Platform

A backend service that accepts long-running jobs through a FastAPI API, queues them in Redis, and processes them on horizontally scalable Celery workers, with retries, exponential backoff and a dead-letter queue. PostgreSQL is the source of truth for job state.

**Stack:** Python, FastAPI, Celery, Redis, PostgreSQL, SQLAlchemy, Pydantic, Docker Compose, Pytest, Locust, Ruff, GitHub Actions

## Architecture

```
Client -> FastAPI (202 Accepted) -> Redis queue -> Celery workers (x N) -> PostgreSQL
                  |                                      |
                  +------------ job status <-------------+
                                     |
                      failed after max retries -> status DEAD (dead-letter queue)
```

- The API saves the job to PostgreSQL, then sends only the job id to Redis.
- Workers load the job, mark it `RUNNING`, run the handler and write the result.
- Failures are retried with exponential backoff (2 s, 4 s, 8 s). After 3 retries the job is marked `DEAD` and kept with its error for inspection and replay.
- `acks_late` and a 60 s Redis visibility timeout let jobs survive a worker crash.

Job states: `QUEUED -> RUNNING -> SUCCESS`, or `RUNNING -> RETRYING -> ... -> DEAD`.

## Quick start

```bash
docker compose up -d --build
docker compose up -d --scale worker=4   # run 4 workers
```

API docs: http://localhost:8000/docs

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type": "fake_io", "payload": {"seconds": 3}}'
```

| Endpoint | Purpose |
|---|---|
| `POST /jobs` | Submit a job (returns 202) |
| `GET /jobs`, `GET /jobs/{id}` | List (filter by `status`) or fetch a job |
| `DELETE /jobs/{id}` | Delete a job (not while running) |
| `GET /dead-letter/jobs` | List jobs that exhausted their retries |
| `POST /dead-letter/jobs/{id}/retry` | Requeue a dead job |

Job types: `fibonacci` (CPU-bound), `fake_io` (simulated I/O), `flaky` (random failures, for failure injection).

## Benchmarks

Environment: MacBook Air M2 16gb ram, Docker Desktop with 8 CPUs and 8 GB. The load generator, API, PostgreSQL, Redis and workers all ran on the same laptop. Each worker container runs one process.

### API latency: queued vs inline

Same job (`fibonacci`, n=32), 10 concurrent users, 30 s, measured with Locust.

| | Inline (work inside the request) | Queued (`POST /jobs`) |
|---|---|---|
| Median | 1,300 ms | 5 ms |
| Average | 1,223 ms | 9 ms |
| 95th percentile | 1,900 ms | 8 ms |
| Failures | 0 | 0 |

The inline baseline is a single uvicorn process, so a multi-process deployment would narrow the gap. Queued submission latency does not depend on how long the job takes.

### Throughput by worker count

1,000 CPU-bound jobs (`fibonacci`, n=32) per run.

| Workers | Throughput | Speedup | Efficiency |
|---|---|---|---|
| 1 | 339 jobs/min | 1.0x | 100% |
| 2 | 658 jobs/min | 1.94x | 97% |
| 4 | ~1,150 jobs/min (two runs: 1,151 and 1,157) | 3.4x | 85% |

Efficiency drops at 4 workers because PostgreSQL, Redis, the API and Docker share the same machine.

### Reliability under injected failures

2,000 `flaky` jobs per run, 4 workers, 4 attempts per job. Failures are random and independent.

| Injected failure rate | Completed | Recovered by retry | Dead-letter |
|---|---|---|---|
| 30% | 99.5% | 598 | 0.5% |
| 50% | 93.5% | 836 | 6.5% |

Both dead-letter rates match theory (0.3^4 is about 0.8%, 0.5^4 is about 6.25%). Jobs that run out of retries are preserved, not lost.

### Crash recovery

Killing a worker mid-job (`docker compose kill worker`) initially left the job stuck in `RUNNING`: with `acks_late`, Redis waits for its visibility timeout (1 hour by default) before redelivering. After setting `visibility_timeout` to 60 s, an interrupted 30 s job was redelivered and completed on the restarted worker in about two minutes.

## Testing

Pytest suite running against a real PostgreSQL database, with Celery's `.delay()` mocked so tests need no Redis. It covers the API, retry and backoff schedule, dead-letter flow and handlers. GitHub Actions runs Ruff and Pytest with coverage against a PostgreSQL service container on every push.

```bash
docker compose up -d db
docker compose exec db psql -U jobflow -d jobflow -c "CREATE DATABASE jobflow_test;"
pytest --cov=app
```

## Reproduce the benchmarks

```bash
locust -f benchmarks/locustfile.py AsyncUser --headless -u 10 -r 10 -t 30s --host http://localhost:8000
python benchmarks/run_benchmark.py --workers 4 --jobs 1000 --type fibonacci --n 32
python benchmarks/run_benchmark.py --workers 4 --jobs 2000 --type flaky --failure-rate 0.3
```

The benchmark script truncates the `jobs` table and flushes Redis before each run. Raw results are in `benchmarks/results/`.

## Limitations

- Everything ran on one laptop, so results show relative scaling, not production capacity.
- Failures were injected randomly; real failures are often correlated, where retries help less.
- A job redelivered after a crash can run twice, so handlers should be idempotent. Idempotency keys are not implemented yet.
- The visibility timeout (60 s) must stay longer than the slowest job.
- Not implemented yet: priority queues, scheduled jobs, monitoring dashboard.