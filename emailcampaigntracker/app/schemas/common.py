from typing import Any, Optional

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class SuccessEnvelope(BaseModel):
    success: bool = True
    data: Any
    request_id: Optional[str] = None

