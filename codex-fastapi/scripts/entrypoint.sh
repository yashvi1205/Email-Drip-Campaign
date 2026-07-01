#!/bin/bash
set -euo pipefail

mkdir -p "${CODEX_HOME}"

if [[ ! -f "${CODEX_HOME}/config.toml" ]]; then
  cat > "${CODEX_HOME}/config.toml" <<'EOF'
cli_auth_credentials_store = "file"
EOF
fi

exec "$@"
