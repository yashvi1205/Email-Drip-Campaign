import logging
import sys
from app.core.settings import get_settings

def setup_logging():
    settings = get_settings()
    
    # Use structured-like formatting for human readability
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-15s | "
        "[req:%(request_id)s] [job:%(job_id)s] - %(message)s"
    )
    
    # Custom Filter to ensure request_id and job_id are always present in record
    class ContextFilter(logging.Filter):
        def filter(self, record):
            if not hasattr(record, "request_id"):
                record.request_id = "none"
            if not hasattr(record, "job_id"):
                record.job_id = "none"
            return True

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if settings.app_env == "production" else logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handlers
    stream_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler("app.log")
    
    # Create and set formatter
    formatter = logging.Formatter(log_format)
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add context filter to handlers
    context_filter = ContextFilter()
    stream_handler.addFilter(context_filter)
    file_handler.addFilter(context_filter)
    
    # Add handlers to root logger
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    root_logger.info("Logging initialized (Env: %s)", settings.app_env)

def get_logger(name: str):
    return logging.getLogger(name)
