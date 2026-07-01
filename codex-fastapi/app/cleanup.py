import asyncio
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)
_MANAGED_WORKSPACE_PREFIXES = ("run-", "session-")


@dataclass(frozen=True)
class CleanupResult:
    deleted: int
    failed: int


def cleanup_workspace(
    workspace_root: Path,
    retention_seconds: int,
    now: datetime | None = None,
) -> CleanupResult:
    if retention_seconds <= 0 or not workspace_root.exists():
        return CleanupResult(deleted=0, failed=0)

    now = now or datetime.now(UTC)
    deleted = 0
    failed = 0

    for path in workspace_root.iterdir():
        if not path.is_dir() or not path.name.startswith(_MANAGED_WORKSPACE_PREFIXES):
            continue

        age_seconds = now.timestamp() - path.stat().st_mtime
        if age_seconds < retention_seconds:
            continue

        try:
            shutil.rmtree(path)
            deleted += 1
            logger.info("Deleted expired workspace directory %s", path)
        except OSError:
            failed += 1
            logger.exception("Failed to delete expired workspace directory %s", path)

    return CleanupResult(deleted=deleted, failed=failed)


async def workspace_cleanup_loop(
    workspace_root: Path,
    retention_seconds: int,
    interval_seconds: int,
) -> None:
    if retention_seconds <= 0 or interval_seconds <= 0:
        logger.info("Workspace cleanup disabled")
        return

    while True:
        result = await asyncio.to_thread(
            cleanup_workspace,
            workspace_root,
            retention_seconds,
        )
        if result.deleted or result.failed:
            logger.info(
                "Workspace cleanup finished: deleted=%d failed=%d",
                result.deleted,
                result.failed,
            )
        await asyncio.sleep(interval_seconds)
