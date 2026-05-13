import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from app.core.settings import get_settings

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class ContextFilter(logging.Filter):
    """Add request and job context to all log records"""

    def __init__(self):
        super().__init__()
        self.request_id: Optional[str] = None
        self.job_id: Optional[str] = None

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id or "none"
        record.job_id = self.job_id or "none"
        record.correlation_id = self.request_id or "N/A"
        return True

    def set_request_context(self, request_id: str, job_id: Optional[str] = None) -> None:
        self.request_id = request_id
        self.job_id = job_id or "none"


class JSONFormatter(logging.Formatter):
    """JSON formatter with structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "none"),
            "job_id": getattr(record, "job_id", "none"),
            "correlation_id": getattr(record, "correlation_id", "N/A"),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging() -> ContextFilter:
    """Configure logging with JSON format when available

    Returns:
        ContextFilter: Filter for setting request context
    """
    settings = get_settings()
    use_json = settings.app_env == "production" and HAS_JSON_LOGGER

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(
        logging.INFO if settings.app_env == "production" else logging.DEBUG
    )

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create context filter
    context_filter = ContextFilter()

    # Create stream handler
    stream_handler = logging.StreamHandler(sys.stdout)

    if use_json:
        formatter = JSONFormatter()
    else:
        log_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | [req:%(request_id)s] [job:%(job_id)s] - %(message)s"
        formatter = logging.Formatter(log_format)

    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    root_logger.addHandler(stream_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    root_logger.info("Logging initialized (Env: %s, JSON: %s)", settings.app_env, use_json)

    return context_filter


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
