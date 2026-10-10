from celery import Celery

from app.config import settings
from app.database import SessionLocal
from app.models import Job, JobStatus, utcnow
from app.tasks.handlers import HANDLERS

celery_app = Celery("jobflow", broker=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="process_job")
def process_job(job_id: int):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or job.status in (JobStatus.SUCCESS, JobStatus.DEAD):
            return

        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        db.commit()

        result = HANDLERS[job.job_type](job.payload)

        job.status = JobStatus.SUCCESS
        job.result = result
        job.completed_at = utcnow()
        db.commit()