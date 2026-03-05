#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[recycle] tearing down services..."
"$ROOT_DIR/ops/scripts/teardown_services.sh"

echo "[recycle] waiting 5 seconds..."
sleep 5

echo "[recycle] standing up services..."
"$ROOT_DIR/ops/scripts/standup_services.sh"

echo "[done] services recycle complete"
