from fastapi import APIRouter

from app.schemas import JobCreate
from app.tasks.handlers import HANDLERS

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.post("/sync")
def run_sync(body: JobCreate):
    """Runs the job inside the request. Exists only as a baseline for load tests."""
    return {"result": HANDLERS[body.job_type](body.payload)}
