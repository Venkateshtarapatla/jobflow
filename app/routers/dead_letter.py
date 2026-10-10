from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import JobOut
from app.worker import process_job

router = APIRouter(prefix="/dead-letter", tags=["dead-letter"])


@router.get("/jobs", response_model=list[JobOut])
def list_dead_jobs(db: Session = Depends(get_db)):
    stmt = select(Job).where(Job.status == JobStatus.DEAD).order_by(Job.id.desc())
    return db.scalars(stmt).all()


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_dead_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != JobStatus.DEAD:
        raise HTTPException(404, "Dead job not found")

    job.status = JobStatus.QUEUED
    job.retry_count = 0
    job.error = None
    job.started_at = None
    job.completed_at = None
    db.commit()
    process_job.delay(job.id)
    return job