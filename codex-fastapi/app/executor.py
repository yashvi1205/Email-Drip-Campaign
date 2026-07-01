import asyncio
import base64
import logging
import mimetypes
import os
import re
import tempfile
from pathlib import Path

import aiofiles

from app.config import EXEC_TIMEOUT_SECONDS, MAX_FILE_BYTES, WORKSPACE_ROOT
from app.models import ExecuteResponse, FileOutput

logger = logging.getLogger(__name__)
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_TEXT_FILE_NAMES = {
    ".dockerignore",
    ".env",
    ".gitignore",
    "dockerfile",
    "makefile",
    "readme",
}
_TEXT_FILE_SUFFIXES = {
    ".bash",
    ".bat",
    ".c",
    ".cfg",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".env",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".log",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def parse_codex_output(stdout: str) -> str:
    lines = stdout.splitlines()

    try:
        start = max(index for index, line in enumerate(lines) if line == "codex") + 1
    except ValueError:
        return stdout.strip()

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index] == "tokens used":
            end = index
            break

    return "\n".join(lines[start:end]).strip()


def _is_text_file(path: Path) -> bool:
    name = path.name.lower()
    if (
        name in _TEXT_FILE_NAMES
        or name.startswith((".env.", "dockerfile."))
        or path.suffix.lower() in _TEXT_FILE_SUFFIXES
    ):
        return True

    content_type, _ = mimetypes.guess_type(path.name)
    return content_type is not None and (
        content_type.startswith("text/")
        or content_type
        in {
            "application/json",
            "application/javascript",
            "application/xml",
            "application/x-sh",
        }
    )


def _file_output(relative_name: str, path: Path, data: bytes) -> FileOutput:
    if _is_text_file(path):
        try:
            return FileOutput(
                name=relative_name,
                content=data.decode("utf-8"),
                encoding="utf-8",
            )
        except UnicodeDecodeError:
            logger.warning("Encoding %s as base64: UTF-8 decoding failed", relative_name)

    return FileOutput(
        name=relative_name,
        content=base64.b64encode(data).decode("ascii"),
        encoding="base64",
    )


async def _read_workspace_files(root: Path) -> list[FileOutput]:
    files: list[FileOutput] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative_name = path.relative_to(root).as_posix()
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            logger.warning(
                "Skipping %s: size %d exceeds limit %d bytes",
                relative_name,
                size,
                MAX_FILE_BYTES,
            )
            continue

        async with aiofiles.open(path, "rb") as handle:
            data = await handle.read()

        files.append(_file_output(relative_name, path, data))

    return files


async def _run_codex(prompt: str, work_dir: Path) -> tuple[str, int]:
    process = await asyncio.create_subprocess_exec(
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        "gpt-5.4-mini",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(work_dir),
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=EXEC_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(
            f"Codex execution timed out after {EXEC_TIMEOUT_SECONDS} seconds"
        ) from None

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if stderr:
        stdout = f"{stdout}\n{stderr}".strip() if stdout else stderr

    return stdout, process.returncode or 0


def _make_tree_accessible(root: Path) -> None:
    for dirpath, _, filenames in os.walk(root):
        os.chmod(dirpath, 0o755)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o644)


def _make_work_dir(session_id: str | None) -> Path:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    if session_id is None:
        return Path(tempfile.mkdtemp(prefix="run-", dir=WORKSPACE_ROOT))

    if not _SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError(
            "session_id must be 1-64 characters: letters, numbers, dot, "
            "underscore, or hyphen"
        )

    work_dir = WORKSPACE_ROOT / f"session-{session_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


async def execute_prompt(
    prompt: str,
    session_id: str | None = None,
    include_stdout: bool = False,
) -> ExecuteResponse:
    work_dir = _make_work_dir(session_id)
    logger.info("Running Codex in %s", work_dir)

    stdout, return_code = await _run_codex(prompt, work_dir)
    _make_tree_accessible(work_dir)
    work_dir.touch()
    files = await _read_workspace_files(work_dir)

    if return_code != 0:
        logger.warning("Codex exited with code %d", return_code)

    return ExecuteResponse(
        output=parse_codex_output(stdout),
        stdout=stdout if include_stdout else None,
        workspace=work_dir.name,
        files=files,
    )
