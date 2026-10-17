"""Submit N jobs, wait until all finish, and report throughput and reliability stats.

Run from the project root with the venv active, for example:
    python benchmarks/run_benchmark.py --workers 4 --jobs 200 --type fake_io --seconds 1
"""

import argparse
import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = ROOT / "benchmarks" / "results" / "throughput.csv"
API_URL = "http://localhost:8000"
DB_URL = "postgresql+psycopg2://jobflow:jobflow@localhost:5432/jobflow"

STATS_SQL = text(
    """
    SELECT
      count(*) AS total,
      count(*) FILTER (WHERE status = 'SUCCESS') AS success,
      count(*) FILTER (WHERE status = 'DEAD') AS dead,
      count(*) FILTER (WHERE status = 'SUCCESS' AND retry_count > 0) AS recovered,
      extract(epoch FROM (max(completed_at) - min(created_at))) AS wall_s,
      avg(extract(epoch FROM (completed_at - started_at))) AS avg_processing_s,
      avg(extract(epoch FROM (started_at - created_at))) AS avg_queue_s
    FROM jobs
    """
)


def run(*command):
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True)


def build_payload(args):
    if args.type == "fake_io":
        return {"seconds": args.seconds}
    if args.type == "fibonacci":
        return {"n": args.n}
    return {"failure_rate": args.failure_rate}


def wait_until_done(engine, total, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with engine.connect() as conn:
            done = conn.execute(
                text("SELECT count(*) FROM jobs WHERE status IN ('SUCCESS', 'DEAD')")
            ).scalar()
        print(f"\r{done}/{total} finished", end="", flush=True)
        if done >= total:
            print()
            return True
        time.sleep(1)
    print()
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workers", type=int, help="scale the worker service to this many containers"
    )
    parser.add_argument("--jobs", type=int, default=200)
    parser.add_argument("--type", choices=["fake_io", "fibonacci", "flaky"], default="fake_io")
    parser.add_argument("--seconds", type=float, default=1.0, help="fake_io sleep time")
    parser.add_argument("--n", type=int, default=32, help="fibonacci input")
    parser.add_argument("--failure-rate", type=float, default=0.3, help="flaky failure rate")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    engine = create_engine(DB_URL)

    if args.workers is not None:
        print(f"Scaling to {args.workers} worker(s)...")
        run("docker", "compose", "up", "-d", "--scale", f"worker={args.workers}", "--no-recreate")
        time.sleep(8)

    print("Resetting queue and jobs table...")
    run("docker", "compose", "exec", "-T", "redis", "redis-cli", "flushall")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE jobs RESTART IDENTITY"))

    body = {"job_type": args.type, "payload": build_payload(args)}
    print(f"Submitting {args.jobs} {args.type} jobs...")
    started = time.time()
    with httpx.Client(base_url=API_URL, timeout=30) as client:
        for _ in range(args.jobs):
            client.post("/jobs", json=body).raise_for_status()
    print(f"Submitted in {time.time() - started:.1f} s")

    if not wait_until_done(engine, args.jobs, args.timeout):
        print("Timed out before all jobs finished. Nothing recorded.")
        sys.exit(1)

    with engine.connect() as conn:
        row = conn.execute(STATS_SQL).one()
    total, success, dead, recovered = row.total, row.success, row.dead, row.recovered
    wall = float(row.wall_s)
    per_minute = total / wall * 60
    avg_processing = float(row.avg_processing_s)
    avg_queue = float(row.avg_queue_s)

    print()
    print(f"Workers:            {args.workers}")
    print(f"Jobs:               {total} ({args.type})")
    print(f"Wall time:          {wall:.1f} s (first submit to last completion)")
    print(f"Throughput:         {per_minute:.0f} jobs/min")
    print(f"Avg processing:     {avg_processing:.2f} s")
    print(f"Avg queue wait:     {avg_queue:.2f} s")
    print(f"SUCCESS:            {success} ({success / total:.1%})")
    print(f"  recovered by retry: {recovered}")
    print(f"DEAD (dead-letter): {dead} ({dead / total:.1%})")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_file = not RESULTS_FILE.exists()
    with RESULTS_FILE.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(
                [
                    "timestamp",
                    "workers",
                    "type",
                    "jobs",
                    "wall_s",
                    "jobs_per_min",
                    "avg_processing_s",
                    "avg_queue_s",
                    "success",
                    "recovered",
                    "dead",
                ]
            )
        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                args.workers,
                args.type,
                total,
                round(wall, 2),
                round(per_minute, 1),
                round(avg_processing, 3),
                round(avg_queue, 3),
                success,
                recovered,
                dead,
            ]
        )


if __name__ == "__main__":
    main()
