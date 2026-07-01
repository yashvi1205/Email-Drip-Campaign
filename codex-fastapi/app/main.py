import asyncio
import logging
import shutil
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from app.auth import AuthStore
from app.cleanup import workspace_cleanup_loop
from app.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    AUTH_DB_PATH,
    LOG_BACKUP_DAYS,
    LOG_DIR,
    WORKSPACE_CLEANUP_INTERVAL_SECONDS,
    WORKSPACE_RETENTION_SECONDS,
    WORKSPACE_ROOT,
)
from app.executor import execute_prompt
from app.logging_config import audit_log, configure_logging
from app.models import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    BatchExecuteRequest,
    BatchExecuteResponse,
    ExecuteRequest,
    ExecuteResponse,
)

configure_logging(LOG_DIR, LOG_BACKUP_DAYS)
logger = logging.getLogger(__name__)

auth_store = AuthStore(AUTH_DB_PATH)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_basic = HTTPBasic(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_store.initialize(ADMIN_USERNAME, ADMIN_PASSWORD)
    if not auth_store.has_admin():
        logger.warning(
            "No admin account configured. Set ADMIN_PASSWORD to enable key management."
        )
    cleanup_task = asyncio.create_task(
        workspace_cleanup_loop(
            WORKSPACE_ROOT,
            WORKSPACE_RETENTION_SECONDS,
            WORKSPACE_CLEANUP_INTERVAL_SECONDS,
        )
    )
    audit_log("server_started")
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        audit_log("server_stopped")


async def get_auth_store() -> AuthStore:
    return auth_store


async def require_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    store: Annotated[AuthStore, Depends(get_auth_store)],
) -> None:
    if not store.authenticate_api_key(api_key):
        audit_log("api_key_auth_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def require_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(admin_basic)],
    store: Annotated[AuthStore, Depends(get_auth_store)],
) -> None:
    username = credentials.username if credentials is not None else None
    if credentials is None or not store.authenticate_admin(
        credentials.username,
        credentials.password,
    ):
        audit_log("admin_auth_failed", username=username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    audit_log("admin_auth_succeeded", username=username)


app = FastAPI(
    title="Codex FastAPI",
    description="Execute Codex prompts via HTTP",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, bool | str]:
    codex_available = shutil.which("codex") is not None
    return {
        "status": "ok" if codex_available else "degraded",
        "codex": codex_available,
    }


@app.post(
    "/execute",
    response_model=ExecuteResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_api_key)],
)
async def execute(request: ExecuteRequest) -> ExecuteResponse:
    logger.info("Executing prompt (%d chars)", len(request.prompt))
    audit_log(
        "execute_requested",
        prompt_chars=len(request.prompt),
        session_id=request.session_id,
    )

    try:
        response = await execute_prompt(
            request.prompt,
            session_id=request.session_id,
            include_stdout=request.include_stdout,
        )
        audit_log(
            "execute_completed",
            workspace=response.workspace,
            session_id=request.session_id,
        )
        return response
    except ValueError as exc:
        audit_log("execute_failed", reason="invalid_session_id")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        audit_log("execute_failed", reason="timeout")
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        audit_log("execute_failed", reason="codex_not_found")
        raise HTTPException(
            status_code=503,
            detail="Codex CLI not found. Ensure @openai/codex is installed.",
        ) from exc
    except Exception as exc:
        logger.exception("Codex execution failed")
        audit_log("execute_failed", reason="unexpected")
        raise HTTPException(status_code=500, detail="Codex execution failed") from exc


@app.post(
    "/execute/batch",
    response_model=BatchExecuteResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_api_key)],
)
async def execute_batch(request: BatchExecuteRequest) -> BatchExecuteResponse:
    prompt_chars = sum(len(prompt) for prompt in request.prompts)
    logger.info(
        "Executing %d prompts in parallel (%d chars)",
        len(request.prompts),
        prompt_chars,
    )
    audit_log(
        "batch_execute_requested",
        prompt_count=len(request.prompts),
        prompt_chars=prompt_chars,
        session_id=request.session_id,
    )

    try:
        results_or_errors = await asyncio.gather(
            *(
                execute_prompt(
                    prompt,
                    session_id=request.session_id,
                    include_stdout=request.include_stdout,
                )
                for prompt in request.prompts
            ),
            return_exceptions=True,
        )
        for result_or_error in results_or_errors:
            if isinstance(result_or_error, Exception):
                raise result_or_error

        results = [
            result
            for result in results_or_errors
            if isinstance(result, ExecuteResponse)
        ]
        audit_log(
            "batch_execute_completed",
            prompt_count=len(request.prompts),
            session_id=request.session_id,
            workspaces=[result.workspace for result in results],
        )
        return BatchExecuteResponse(results=results)
    except ValueError as exc:
        audit_log("batch_execute_failed", reason="invalid_session_id")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        audit_log("batch_execute_failed", reason="timeout")
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        audit_log("batch_execute_failed", reason="codex_not_found")
        raise HTTPException(
            status_code=503,
            detail="Codex CLI not found. Ensure @openai/codex is installed.",
        ) from exc
    except Exception as exc:
        logger.exception("Batch Codex execution failed")
        audit_log("batch_execute_failed", reason="unexpected")
        raise HTTPException(status_code=500, detail="Codex execution failed") from exc


@app.post(
    "/admin/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_api_key(
    request: ApiKeyCreateRequest,
    store: Annotated[AuthStore, Depends(get_auth_store)],
) -> ApiKeyCreateResponse:
    created = store.create_api_key(request.name)
    audit_log("api_key_created", key_id=created.id, key_prefix=created.prefix)
    return ApiKeyCreateResponse(
        id=created.id,
        name=created.name,
        key=created.key,
        prefix=created.prefix,
        created_at=created.created_at,
    )


@app.get(
    "/admin/api-keys",
    response_model=list[ApiKeyResponse],
    dependencies=[Depends(require_admin)],
)
async def list_api_keys(
    store: Annotated[AuthStore, Depends(get_auth_store)],
) -> list[ApiKeyResponse]:
    return [
        ApiKeyResponse(
            id=record.id,
            name=record.name,
            prefix=record.prefix,
            created_at=record.created_at,
            last_used_at=record.last_used_at,
            revoked_at=record.revoked_at,
        )
        for record in store.list_api_keys()
    ]


@app.delete(
    "/admin/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def revoke_api_key(
    key_id: str,
    store: Annotated[AuthStore, Depends(get_auth_store)],
) -> None:
    if not store.revoke_api_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")
    audit_log("api_key_revoked", key_id=key_id)
