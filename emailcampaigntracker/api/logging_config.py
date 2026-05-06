import logging
import os
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


def configure_logging(request_id_getter, level: Optional[str] = None) -> None:
    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
    )
    root = logging.getLogger()
    root.addFilter(_RequestIdFilter(request_id_getter))

