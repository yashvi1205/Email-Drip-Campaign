from datetime import UTC, datetime, timedelta

from app.cleanup import cleanup_workspace


def test_cleanup_workspace_removes_old_run_directories(tmp_path) -> None:
    old_run = tmp_path / "run-old"
    old_run.mkdir()
    old_file = old_run / "output.txt"
    old_file.write_text("old")

    old_session = tmp_path / "session-old"
    old_session.mkdir()
    old_session_file = old_session / "output.txt"
    old_session_file.write_text("old session")

    recent_run = tmp_path / "run-recent"
    recent_run.mkdir()
    recent_file = recent_run / "output.txt"
    recent_file.write_text("recent")

    unrelated = tmp_path / "manual"
    unrelated.mkdir()

    now = datetime.now(UTC)
    old_time = now - timedelta(days=3)
    recent_time = now - timedelta(minutes=5)

    old_timestamp = old_time.timestamp()
    recent_timestamp = recent_time.timestamp()
    old_file.touch()
    old_session_file.touch()
    recent_file.touch()
    old_run.touch()
    old_session.touch()
    recent_run.touch()

    import os

    os.utime(old_file, (old_timestamp, old_timestamp))
    os.utime(old_run, (old_timestamp, old_timestamp))
    os.utime(old_session_file, (old_timestamp, old_timestamp))
    os.utime(old_session, (old_timestamp, old_timestamp))
    os.utime(recent_file, (recent_timestamp, recent_timestamp))
    os.utime(recent_run, (recent_timestamp, recent_timestamp))

    result = cleanup_workspace(
        tmp_path,
        retention_seconds=24 * 60 * 60,
        now=now,
    )

    assert result.deleted == 2
    assert result.failed == 0
    assert old_run.exists() is False
    assert old_session.exists() is False
    assert recent_run.exists() is True
    assert unrelated.exists() is True


def test_cleanup_workspace_is_disabled_when_retention_is_zero(tmp_path) -> None:
    old_run = tmp_path / "run-old"
    old_run.mkdir()

    result = cleanup_workspace(tmp_path, retention_seconds=0)

    assert result.deleted == 0
    assert result.failed == 0
    assert old_run.exists() is True
