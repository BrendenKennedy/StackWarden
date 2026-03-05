#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=ops/scripts/service_lib.sh
source "$ROOT_DIR/ops/scripts/service_lib.sh"

ensure_dirs

start_backend
start_frontend

echo "[done] services standup complete"
