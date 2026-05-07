from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class ScraperJobStatusResponse(BaseModel):
    job_id: int = Field(..., alias="id")
    status: str
    source: str
    webhook_url: Optional[str] = None
    attempts: int
    max_attempts: int
    cancelled: bool
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_error: Optional[str] = None
    rq_job_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class ScraperJobCancelResponse(BaseModel):
    ok: bool
    status: str
    job_id: int

