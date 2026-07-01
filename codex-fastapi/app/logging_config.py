import json
import logging
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

AUDIT_LOGGER_NAME = "app.audit"


def configure_logging(log_dir: Path, backup_days: int) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    app_handler = TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        backupCount=backup_days,
        encoding="utf-8",
        utc=True,
    )
    app_handler.setFormatter(formatter)
    root.addHandler(app_handler)

    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)
    audit_logger.setLevel(logging.INFO)
    audit_logger.handlers.clear()
    audit_logger.propagate = False

    audit_handler = TimedRotatingFileHandler(
        log_dir / "audit.log",
        when="midnight",
        backupCount=backup_days,
        encoding="utf-8",
        utc=True,
    )
    audit_handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(audit_handler)


def audit_log(event: str, **fields: Any) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    logging.getLogger(AUDIT_LOGGER_NAME).info(
        json.dumps(record, sort_keys=True, separators=(",", ":"))
    )
