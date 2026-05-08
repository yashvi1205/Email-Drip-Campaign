from typing import Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class ScrapeStartRequest(BaseModel):
    webhook_url: Optional[str] = None
    source: str = Field(default="unknown", max_length=128)


class ScraperStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: Optional[str] = None
    message: Optional[str] = None
    new_posts_found: Optional[int] = None
    error: Optional[str] = None


class ScraperStatusUpdateResponse(BaseModel):
    ok: bool


class ScrapeStartResponse(BaseModel):
    status: str
    job_id: Optional[int] = None
    source: Optional[str] = None
    webhook_url: Optional[str] = None


class GenericStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    new_posts_found: Optional[int] = None
    error: Optional[str] = None


