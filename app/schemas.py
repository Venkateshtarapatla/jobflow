from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import JobStatus


class JobCreate(BaseModel):
    job_type: Literal["fibonacci", "fake_io", "flaky"]
    payload: dict = Field(default_factory=dict)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: JobStatus
    payload: dict
    result: dict | None
    error: str | None
    retry_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
