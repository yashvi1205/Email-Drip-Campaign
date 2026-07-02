# Codex FastAPI

HTTP API that runs [OpenAI Codex CLI](https://github.com/openai/codex) in non-interactive mode and returns generated files plus optional stdout.

Each request spawns an isolated run directory, executes:

```bash
codex exec --dangerously-bypass-approvals-and-sandbox "<prompt>"
```

and collects all files created in that directory. Textual files are returned as UTF-8 content; binary files are returned as base64-encoded strings.

## Prerequisites

- **Docker path (recommended):** Docker Engine + Docker Compose v2
- **Local path:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+, `@openai/codex` CLI

## Quick start (Docker)

```bash
export ADMIN_PASSWORD='change-me'
./scripts/setup.sh
```

This script:

1. Builds the image (Ubuntu, Node.js, Codex CLI, Python/uv, FastAPI)
2. Runs one-time `codex login --device-auth` if `./codex-home/auth.json` is missing
3. Starts the API on port 8000

Day-to-day:

```bash
docker compose up -d      # start
docker compose down       # stop
docker compose logs -f    # tail logs
```

Verify:

```bash
curl http://localhost:8000/health
curl -u admin:$ADMIN_PASSWORD \
  -H 'Content-Type: application/json' \
  -d '{"name": "local-dev"}' \
  http://localhost:8000/admin/api-keys
curl -X POST http://localhost:8000/execute \
  -H "X-API-Key: $CODEX_FASTAPI_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "create hello.py that prints hello world"}'
curl -X POST http://localhost:8000/execute/batch \
  -H "X-API-Key: $CODEX_FASTAPI_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompts": ["create hello.py", "create goodbye.py"], "session_id": "deal-123"}'
```

Interactive API docs: http://localhost:8000/docs

## Project layout

```
codex-fastapi/
├── app/
│   ├── main.py        # FastAPI routes
│   ├── executor.py    # async subprocess + aiofiles file capture
│   ├── models.py      # request/response schemas
│   └── config.py      # environment configuration
├── scripts/
│   ├── setup.sh       # one-time Docker bootstrap
│   └── entrypoint.sh  # seeds Codex file-based auth config
├── workspace/         # persisted run output (gitignored)
├── codex-home/        # Codex CLI credentials (gitignored)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## API reference

### `GET /health`

Liveness check. Returns `codex: true` when the Codex CLI binary is on `PATH`.

```json
{"status": "ok", "codex": true}
```

### `POST /execute`

Requires `X-API-Key`.

**Request**

```json
{
  "prompt": "create hello.py that prints hello world",
  "session_id": "deal-123",
  "include_stdout": false
}
```

`session_id` is optional. When omitted, the server creates a fresh isolated
`run-*` directory for the request. When provided, all requests with the same
`session_id` reuse `session-<session_id>` under `WORKSPACE_ROOT`, so later
agents can read files created by earlier agents without resending them.

**Response**

```json
{
  "output": "...",
  "workspace": "run-abc123",
  "files": [
    {
      "name": "hello.py",
      "content": "print(\"hello world\")\n",
      "encoding": "utf-8"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `prompt` | Prompt passed to Codex exec |
| `session_id` | Optional filename-safe key for reusing a working directory |
| `include_stdout` | Optional flag to include raw combined stdout/stderr in the response |
| `output` | Final assistant message parsed from Codex output |
| `stdout` | Combined Codex stdout/stderr, present only when `include_stdout` is `true` |
| `workspace` | Run directory name (under `WORKSPACE_ROOT`) |
| `files[].name` | Relative path within the run directory |
| `files[].content` | UTF-8 text for textual files, otherwise base64-encoded bytes |
| `files[].encoding` | `utf-8` or `base64` |

**On disk:** files persist at `workspace/<workspace>/` (e.g. `workspace/run-abc123/hello.py`).

**Errors**

| Status | Cause |
|--------|-------|
| `401` | Missing, invalid, or revoked API key |
| `422` | Empty or missing `prompt` |
| `503` | Codex CLI not found |
| `504` | Execution exceeded `EXEC_TIMEOUT_SECONDS` |
| `500` | Unexpected execution failure |

### `POST /execute/batch`

Requires `X-API-Key`.

Runs one Codex exec instance per prompt concurrently. When `session_id` is
omitted, each prompt gets its own isolated `run-*` workspace. When `session_id`
is provided, every prompt uses the same `session-<session_id>` workspace.
`results` are returned in the same order as the input prompts.

**Request**

```json
{
  "prompts": [
    "create hello.py that prints hello world",
    "create goodbye.py that prints goodbye"
  ],
  "session_id": "deal-123",
  "include_stdout": false
}
```

**Response**

```json
{
  "results": [
    {
      "output": "...",
      "workspace": "run-abc123",
      "files": []
    },
    {
      "output": "...",
      "workspace": "run-def456",
      "files": []
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `prompts` | Non-empty list of prompts passed to parallel Codex exec runs |
| `session_id` | Optional filename-safe key; when present, every prompt uses the same session workspace |
| `include_stdout` | Optional flag to include raw combined stdout/stderr in each response |
| `results` | Per-prompt responses in the same order as `prompts` |

Batch errors use the same status codes as `POST /execute`.

## Configuration

Copy `.env.example` to `.env` before starting Docker Compose. Keep `.env`
local; it is gitignored because it can contain secrets such as
`ADMIN_PASSWORD`.

| Variable | Default (Docker) | Default (local) | Description |
|----------|------------------|-----------------|-------------|
| `WORKSPACE_ROOT` | `/workspace` | `./workspace` | Base directory for per-request `run-*/` and session-scoped `session-*/` folders |
| `CODEX_HOME` | `/codex-home` | `~/.codex` | Codex CLI config and cached credentials |
| `EXEC_TIMEOUT_SECONDS` | `1800` | `1800` | Max Codex runtime per request |
| `MAX_FILE_BYTES` | `10485760` (10 MB) | `10485760` | Files larger than this are skipped in the response |
| `AUTH_DB_PATH` | `/workspace/auth.sqlite3` | `./auth.sqlite3` | SQLite database for admin and API key hashes |
| `ADMIN_USERNAME` | `admin` | `admin` | Admin username for key management |
| `ADMIN_PASSWORD` | unset | unset | Admin password used to create/update the admin account |
| `WORKSPACE_RETENTION_SECONDS` | `86400` | `86400` | Delete managed `run-*` and `session-*` workspace directories older than this; set `0` to disable |
| `WORKSPACE_CLEANUP_INTERVAL_SECONDS` | `3600` | `3600` | How often the background cleanup task scans the workspace |
| `LOG_DIR` | `/workspace/logs` | `./logs` | Directory for `app.log` and `audit.log` |
| `LOG_BACKUP_DAYS` | `14` | `14` | Number of daily rotated log files to keep |

Docker Compose mounts:

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `./workspace` | `/workspace` | Codex run output |
| `./codex-home` | `/codex-home` | Codex CLI auth + config |

## Cleanup and logging

On startup, the API runs a background cleanup task that scans `WORKSPACE_ROOT`
every `WORKSPACE_CLEANUP_INTERVAL_SECONDS` and deletes only managed `run-*` and
`session-*` directories older than `WORKSPACE_RETENTION_SECONDS`. Other
directories are ignored.

Application logs are written to `LOG_DIR/app.log`. Security-relevant audit
events are written as JSON lines to `LOG_DIR/audit.log`. Both files rotate daily
at midnight UTC and keep `LOG_BACKUP_DAYS` old files.

Audit events intentionally avoid secrets and full request bodies. They include
events such as server start/stop, API key auth failures, admin auth attempts,
key creation/revocation, and execution failures.

## Authentication

The HTTP API uses application API keys for Codex execution and an admin account
for key management. Keys and admin passwords are stored in SQLite as hashes;
plaintext API keys are returned only once at creation time.

### Admin bootstrap

Set `ADMIN_PASSWORD` before starting the server. `ADMIN_USERNAME` defaults to
`admin`. On startup, the server creates or updates that admin account in SQLite.
If `ADMIN_PASSWORD` is not set, key management is unavailable until an admin
exists.

```bash
cp .env.example .env
# edit .env and set ADMIN_PASSWORD
docker compose up -d
```

The SQLite database defaults to `/workspace/auth.sqlite3` in Docker and
`./auth.sqlite3` locally. Override with `AUTH_DB_PATH` if needed.

### Create an API key

```bash
curl -u admin:$ADMIN_PASSWORD \
  -H 'Content-Type: application/json' \
  -d '{"name": "ci"}' \
  http://localhost:8000/admin/api-keys
```

The response contains `key` once. Store it securely; it cannot be recovered from
SQLite later.

### Use an API key

```bash
curl -X POST http://localhost:8000/execute \
  -H "X-API-Key: $CODEX_FASTAPI_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "create hello.py that prints hello world"}'
```

### List and revoke keys

```bash
curl -u admin:$ADMIN_PASSWORD http://localhost:8000/admin/api-keys
curl -u admin:$ADMIN_PASSWORD -X DELETE http://localhost:8000/admin/api-keys/<key-id>
```

## Codex CLI authentication

Uses **Codex CLI login** (ChatGPT/device auth), not `CODEX_API_KEY`.

| Environment | Setup | Persistence |
|-------------|-------|-------------|
| Docker | `./scripts/setup.sh` or `docker compose run --rm -it api codex login --device-auth` | `./codex-home/` |
| Local | `codex login` on host | `~/.codex/` |

**Reuse host credentials in Docker:**

```bash
mkdir -p codex-home
cp -a ~/.codex/. codex-home/
docker compose up --build -d
```

**Browser login in Docker** (requires port publish for OAuth callback):

```bash
docker compose run --rm -it -p 1455:1455 api codex login
```

The container entrypoint seeds `cli_auth_credentials_store = "file"` so credentials are stored on disk (OS keyring is unavailable inside containers).

## Local development

```bash
npm install -g @openai/codex
codex login
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Granian also works, but FastAPI must be served with the ASGI interface:

```bash
uv run granian --interface asgi app.main:app
```

## Security notes

- Codex runs with `--dangerously-bypass-approvals-and-sandbox`, giving **full filesystem and command access** within the run directory and container. Docker provides the outer isolation boundary.
- Do **not** expose this API to the public internet without authentication and network controls.
- Treat `./codex-home/auth.json` as a secret. It is gitignored and excluded from the Docker build context.
- Requests without `session_id` create a new `run-*/` directory. Requests with `session_id` reuse `session-*/`. Old managed workspaces are auto-deleted according to `WORKSPACE_RETENTION_SECONDS`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `address already in use` on port 8000 | `fuser -k 8000/tcp` then `docker compose up -d` |
| OAuth callback fails (`localhost:1455` refused) | Use `codex login --device-auth` instead |
| `codex: false` in `/health` | Rebuild image: `docker compose up --build -d` |
| Permission denied on `workspace/run-*` | Rebuild after latest changes (permissions are fixed post-run) |
| Re-login required | `docker compose run --rm -it api codex login --device-auth` |

## Implementation notes

- **Subprocess:** `asyncio.create_subprocess_exec` with async timeout
- **File I/O:** `aiofiles` for reading generated files
- **Dependencies:** managed with `uv` (`pyproject.toml` + `uv.lock`)
- **Codex version:** pinned to `0.139.0` in the Dockerfile
