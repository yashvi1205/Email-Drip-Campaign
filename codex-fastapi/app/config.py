import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_WORKSPACE = _PROJECT_ROOT / "workspace"
_DEFAULT_AUTH_DB = _PROJECT_ROOT / "auth.sqlite3"
_DEFAULT_LOG_DIR = _PROJECT_ROOT / "logs"

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(_DEFAULT_WORKSPACE)))
EXEC_TIMEOUT_SECONDS = int(os.environ.get("EXEC_TIMEOUT_SECONDS", "600"))
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", str(10 * 1024 * 1024)))
AUTH_DB_PATH = Path(os.environ.get("AUTH_DB_PATH", str(_DEFAULT_AUTH_DB)))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or None
WORKSPACE_RETENTION_SECONDS = int(
    os.environ.get("WORKSPACE_RETENTION_SECONDS", str(24 * 60 * 60))
)
WORKSPACE_CLEANUP_INTERVAL_SECONDS = int(
    os.environ.get("WORKSPACE_CLEANUP_INTERVAL_SECONDS", str(60 * 60))
)
LOG_DIR = Path(os.environ.get("LOG_DIR", str(_DEFAULT_LOG_DIR)))
LOG_BACKUP_DAYS = int(os.environ.get("LOG_BACKUP_DAYS", "14"))
