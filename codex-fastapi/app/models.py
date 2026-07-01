from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt passed to Codex exec")
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        description=(
            "Optional filename-safe session key. Requests with the same session_id "
            "reuse the same working directory and files."
        ),
    )
    include_stdout: bool = Field(
        default=False,
        description="Include raw combined Codex stdout/stderr in the response",
    )


class BatchExecuteRequest(BaseModel):
    prompts: list[str] = Field(
        ...,
        min_length=1,
        description="Prompts passed to parallel Codex exec runs",
    )
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
        description=(
            "Optional filename-safe session key. When provided, every prompt in "
            "the batch uses the same working directory and files."
        ),
    )
    include_stdout: bool = Field(
        default=False,
        description="Include raw combined Codex stdout/stderr in each response",
    )


class FileOutput(BaseModel):
    name: str = Field(..., description="Relative path within the working directory")
    content: str = Field(..., description="File contents")
    encoding: str = Field(
        default="base64",
        description="'utf-8' for textual files, 'base64' for binary files",
    )


class ExecuteResponse(BaseModel):
    output: str = Field(..., description="Final assistant message parsed from Codex output")
    stdout: str | None = Field(
        default=None,
        description="Raw combined Codex stdout/stderr when requested",
    )
    workspace: str = Field(
        ...,
        description="Run directory name under WORKSPACE_ROOT (e.g. run-abc123)",
    )
    files: list[FileOutput]


class BatchExecuteResponse(BaseModel):
    results: list[ExecuteResponse] = Field(
        ...,
        description="Codex exec responses in the same order as the input prompts",
    )


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Human-readable label for the API key",
    )


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    key: str = Field(..., description="Plaintext key. Returned only once.")
    prefix: str
    created_at: str


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: str | None
    revoked_at: str | None
