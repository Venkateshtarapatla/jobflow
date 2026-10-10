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


@celery_app.task(bind=True, name="process_job", max_retries=settings.max_retries)
def process_job(self, job_id: int):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or job.status in (JobStatus.SUCCESS, JobStatus.DEAD):
            return

        job.status = JobStatus.RUNNING
        job.started_at = job.started_at or utcnow()
        db.commit()

        try:
            result = HANDLERS[job.job_type](job.payload)
        except Exception as exc:
            job.error = f"{type(exc).__name__}: {exc}"
            attempt = self.request.retries  # 0 on the first attempt

            if attempt >= self.max_retries:
                job.status = JobStatus.DEAD
                job.completed_at = utcnow()
                db.commit()
                return

            job.status = JobStatus.RETRYING
            job.retry_count = attempt + 1
            db.commit()

            countdown = 2 ** (attempt + 1)  # 2s, 4s, 8s
            raise self.retry(exc=exc, countdown=countdown)

        job.status = JobStatus.SUCCESS
        job.result = result
        job.error = None
        job.completed_at = utcnow()
        db.commit()