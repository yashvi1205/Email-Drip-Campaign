from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.middleware.request_context import get_request_id


def _error_code_from_status(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
    }
    return mapping.get(status_code, f"HTTP_{status_code}")


async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = get_request_id()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": _error_code_from_status(exc.status_code),
                "message": str(exc.detail),
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id or ""},
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = get_request_id()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": _error_code_from_status(exc.status_code),
                "message": str(exc.detail),
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id or ""},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id()
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id or ""},
    )

