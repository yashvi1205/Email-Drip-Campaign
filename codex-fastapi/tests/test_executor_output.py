import base64

import pytest

from app import executor
from app.models import FileOutput
from app.executor import parse_codex_output


def test_parse_codex_output_extracts_final_assistant_message() -> None:
    stdout = """Hi. What would you like me to work on?

OpenAI Codex v0.138.0
--------
workdir: /tmp/run
model: gpt-5.5
--------
user
Hi
codex
Hi. What would you like me to work on?
tokens used
6,008"""

    assert parse_codex_output(stdout) == "Hi. What would you like me to work on?"


def test_parse_codex_output_keeps_multiline_assistant_message() -> None:
    stdout = """OpenAI Codex v0.138.0
--------
user
write a list
codex
One
Two
Three
tokens used
123"""

    assert parse_codex_output(stdout) == "One\nTwo\nThree"


def test_parse_codex_output_falls_back_to_trimmed_stdout() -> None:
    assert parse_codex_output("plain output\n") == "plain output"


@pytest.mark.asyncio
async def test_read_workspace_files_returns_text_files_as_utf8(tmp_path) -> None:
    (tmp_path / ".env").write_text("TOKEN=test\n")
    (tmp_path / "README.md").write_text("# Notes\n\nHello\n")
    (tmp_path / "script.py").write_text("print('hello')\n")

    files = await executor._read_workspace_files(tmp_path)

    assert [(file.name, file.content, file.encoding) for file in files] == [
        (".env", "TOKEN=test\n", "utf-8"),
        ("README.md", "# Notes\n\nHello\n", "utf-8"),
        ("script.py", "print('hello')\n", "utf-8"),
    ]


@pytest.mark.asyncio
async def test_read_workspace_files_keeps_binary_files_base64(tmp_path) -> None:
    (tmp_path / "image.png").write_bytes(b"\x00\xff")

    files = await executor._read_workspace_files(tmp_path)

    assert len(files) == 1
    assert files[0].name == "image.png"
    assert files[0].content == base64.b64encode(b"\x00\xff").decode("ascii")
    assert files[0].encoding == "base64"


@pytest.mark.asyncio
async def test_execute_prompt_reuses_session_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(executor, "WORKSPACE_ROOT", tmp_path)
    work_dirs = []

    async def fake_run_codex(prompt, work_dir):
        work_dirs.append(work_dir)
        if prompt == "prospect":
            (work_dir / "PROSPECT-ANALYSIS.md").write_text("prospect data")
        else:
            assert (work_dir / "PROSPECT-ANALYSIS.md").read_text() == "prospect data"
            (work_dir / "OUTREACH-SEQUENCE.md").write_text("outreach data")
        return f"codex\n{prompt} done\ntokens used", 0

    async def fake_read_workspace_files(work_dir):
        return [
            FileOutput(name=path.name, content="")
            for path in sorted(work_dir.iterdir())
            if path.is_file()
        ]

    monkeypatch.setattr(executor, "_run_codex", fake_run_codex)
    monkeypatch.setattr(executor, "_read_workspace_files", fake_read_workspace_files)

    first = await executor.execute_prompt("prospect", session_id="deal-123")
    second = await executor.execute_prompt("outreach", session_id="deal-123")

    assert first.workspace == "session-deal-123"
    assert second.workspace == "session-deal-123"
    assert work_dirs == [tmp_path / "session-deal-123", tmp_path / "session-deal-123"]
    assert {file.name for file in second.files} == {
        "OUTREACH-SEQUENCE.md",
        "PROSPECT-ANALYSIS.md",
    }
    assert second.stdout is None


@pytest.mark.asyncio
async def test_execute_prompt_includes_stdout_when_requested(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(executor, "WORKSPACE_ROOT", tmp_path)

    async def fake_run_codex(prompt, work_dir):
        return "codex\nhello\ntokens used", 0

    async def fake_read_workspace_files(work_dir):
        return []

    monkeypatch.setattr(executor, "_run_codex", fake_run_codex)
    monkeypatch.setattr(executor, "_read_workspace_files", fake_read_workspace_files)

    response = await executor.execute_prompt("hello", include_stdout=True)

    assert response.output == "hello"
    assert response.stdout == "codex\nhello\ntokens used"


@pytest.mark.asyncio
async def test_execute_prompt_rejects_unsafe_session_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(executor, "WORKSPACE_ROOT", tmp_path)

    with pytest.raises(ValueError):
        await executor.execute_prompt("hello", session_id="../outside")
