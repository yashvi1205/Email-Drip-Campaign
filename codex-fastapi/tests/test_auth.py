import asyncio
import sqlite3
from pathlib import Path

import httpx
import pytest

from app.auth import AuthStore
from app.models import ExecuteResponse
from app.main import app, get_auth_store
import app.main as main_module


def make_store(tmp_path: Path) -> AuthStore:
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.initialize("admin", "secret-admin-password")

    async def override_auth_store() -> AuthStore:
        return store

    app.dependency_overrides[get_auth_store] = override_auth_store
    return store


@pytest.mark.asyncio
async def test_execute_requires_api_key(tmp_path: Path) -> None:
    make_store(tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post("/execute", json={"prompt": "hello"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_create_list_and_revoke_api_key(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        create_response = await client.post(
            "/admin/api-keys",
            auth=("admin", "secret-admin-password"),
            json={"name": "automation"},
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["key"].startswith("cdx_")
        assert store.authenticate_api_key(created["key"]) is True

        list_response = await client.get(
            "/admin/api-keys",
            auth=("admin", "secret-admin-password"),
        )
        assert list_response.status_code == 200
        keys = list_response.json()
        assert keys == [
            {
                "id": created["id"],
                "name": "automation",
                "prefix": created["prefix"],
                "created_at": created["created_at"],
                "last_used_at": keys[0]["last_used_at"],
                "revoked_at": None,
            }
        ]

        revoke_response = await client.delete(
            f"/admin/api-keys/{created['id']}",
            auth=("admin", "secret-admin-password"),
        )
        assert revoke_response.status_code == 204
        assert store.authenticate_api_key(created["key"]) is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_execute_stdout_is_omitted_unless_requested(tmp_path: Path, monkeypatch) -> None:
    store = make_store(tmp_path)
    api_key = store.create_api_key("automation").key
    transport = httpx.ASGITransport(app=app)

    async def fake_execute_prompt(
        prompt: str,
        session_id: str | None = None,
        include_stdout: bool = False,
    ) -> ExecuteResponse:
        return ExecuteResponse(
            output="done",
            stdout="raw logs" if include_stdout else None,
            workspace="run-test",
            files=[],
        )

    monkeypatch.setattr(main_module, "execute_prompt", fake_execute_prompt)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-API-Key": api_key},
    ) as client:
        default_response = await client.post("/execute", json={"prompt": "hello"})
        stdout_response = await client.post(
            "/execute",
            json={"prompt": "hello", "include_stdout": True},
        )

    assert default_response.status_code == 200
    assert "stdout" not in default_response.json()
    assert stdout_response.status_code == 200
    assert stdout_response.json()["stdout"] == "raw logs"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_batch_execute_runs_prompts_in_parallel_and_preserves_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = make_store(tmp_path)
    api_key = store.create_api_key("automation").key
    transport = httpx.ASGITransport(app=app)
    active_count = 0
    max_active_count = 0
    session_ids = []

    async def fake_execute_prompt(
        prompt: str,
        session_id: str | None = None,
        include_stdout: bool = False,
    ) -> ExecuteResponse:
        nonlocal active_count, max_active_count
        session_ids.append(session_id)
        active_count += 1
        max_active_count = max(max_active_count, active_count)
        await asyncio.sleep(0.01)
        active_count -= 1

        return ExecuteResponse(
            output=f"{prompt} done",
            stdout=f"{prompt} logs" if include_stdout else None,
            workspace=f"run-{prompt}",
            files=[],
        )

    monkeypatch.setattr(main_module, "execute_prompt", fake_execute_prompt)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-API-Key": api_key},
    ) as client:
        response = await client.post(
            "/execute/batch",
            json={
                "prompts": ["one", "two", "three"],
                "session_id": "deal-123",
                "include_stdout": True,
            },
        )

    assert response.status_code == 200
    assert max_active_count > 1
    assert session_ids == ["deal-123", "deal-123", "deal-123"]
    assert response.json() == {
        "results": [
            {
                "output": "one done",
                "stdout": "one logs",
                "workspace": "run-one",
                "files": [],
            },
            {
                "output": "two done",
                "stdout": "two logs",
                "workspace": "run-two",
                "files": [],
            },
            {
                "output": "three done",
                "stdout": "three logs",
                "workspace": "run-three",
                "files": [],
            },
        ]
    }
    app.dependency_overrides.clear()


def test_api_key_plaintext_is_not_stored(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    created = store.create_api_key("ci")

    with sqlite3.connect(tmp_path / "auth.sqlite3") as connection:
        row = connection.execute(
            "SELECT key_hash, prefix FROM api_keys WHERE id = ?",
            (created.id,),
        ).fetchone()

    assert row is not None
    assert row[0] != created.key
    assert created.key not in row
    assert row[1] == created.prefix
    app.dependency_overrides.clear()


def test_admin_password_is_not_stored(tmp_path: Path) -> None:
    make_store(tmp_path)

    with sqlite3.connect(tmp_path / "auth.sqlite3") as connection:
        row = connection.execute(
            "SELECT password_hash, salt FROM admins WHERE username = 'admin'"
        ).fetchone()

    assert row is not None
    assert row[0] != "secret-admin-password"
    assert row[1] != "secret-admin-password"
    app.dependency_overrides.clear()
