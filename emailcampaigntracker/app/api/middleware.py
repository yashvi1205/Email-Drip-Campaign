"""Middleware for request tracing and correlation IDs"""

import uuid
import time
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.metrics import record_request_metric


logger = logging.getLogger(__name__)
context_filter = None


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Add correlation ID and request timing to all requests"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or create correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(
            uuid.uuid4()
        )
        request.state.correlation_id = correlation_id

        # Set correlation ID in logging context
        if context_filter:
            context_filter.set_request_context(correlation_id)

        # Record request start time
        start_time = time.time()

        # Call the next middleware/handler
        response = await call_next(request)

        # Calculate request duration
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # Record metrics
        record_request_metric(
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Log request summary
        logger.info(
            "HTTP %s %s %s - %dms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response


def setup_tracing_middleware(app, logging_context_filter):
    """Setup request tracing middleware with logging context"""
    global context_filter
    context_filter = logging_context_filter
    app.add_middleware(RequestTracingMiddleware)
