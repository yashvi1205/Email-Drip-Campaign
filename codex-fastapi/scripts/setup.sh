#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p workspace codex-home

echo "Building image..."
docker compose build

if [[ -f codex-home/auth.json ]]; then
  echo "Codex credentials already present in ./codex-home — skipping login."
else
  echo "One-time setup: sign in to Codex."
  echo "Use the device code shown below; credentials are saved to ./codex-home for reuse."
  docker compose run --rm -it api codex login --device-auth
fi

docker compose up -d "$@"
echo "API ready at http://localhost:8000"
