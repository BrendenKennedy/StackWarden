#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=ops/scripts/service_lib.sh
source "$ROOT_DIR/ops/scripts/service_lib.sh"

ensure_dirs

stop_service "$FRONTEND_NAME" "$FRONTEND_PIDFILE" "$FRONTEND_HOST" "$FRONTEND_PORT"
stop_service "$BACKEND_NAME" "$BACKEND_PIDFILE" "$BACKEND_HOST" "$BACKEND_PORT"

echo "[done] services teardown complete"
