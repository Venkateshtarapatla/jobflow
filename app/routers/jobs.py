from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import JobCreate, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    job = Job(job_type=body.job_type, payload=body.payload, status=JobStatus.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)
    # Step 3: enqueue the job here, AFTER the commit
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    status_filter: JobStatus | None = Query(None, alias="status"),
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Job).order_by(Job.id.desc()).limit(limit).offset(offset)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    return db.scalars(stmt).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status == JobStatus.RUNNING:
        raise HTTPException(409, "Cannot delete a running job")
    db.delete(job)
    db.commit()