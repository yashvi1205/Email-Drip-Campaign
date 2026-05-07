import logging
import os
import json
from typing import Optional


class _RequestIdFilter(logging.Filter):
    def __init__(self, request_id_getter):
        super().__init__()
        self._get_request_id = request_id_getter

    def filter(self, record: logging.LogRecord) -> bool:
        rid = None
        try:
            rid = self._get_request_id()
        except Exception:
            rid = None
        record.request_id = rid or "-"
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(request_id_getter, level: Optional[str] = None) -> None:
    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    json_logs = os.getenv("LOG_JSON", "false").lower() == "true"

    if json_logs:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logging.basicConfig(level=log_level, handlers=[handler], force=True)
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
            force=True,
        )
    root = logging.getLogger()
    root.addFilter(_RequestIdFilter(request_id_getter))

