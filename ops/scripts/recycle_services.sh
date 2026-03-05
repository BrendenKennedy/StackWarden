#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

MAX_ATTEMPTS="${STACKWARDEN_RECYCLE_MAX_ATTEMPTS:-3}"
RETRY_DELAY_SEC="${STACKWARDEN_RECYCLE_RETRY_DELAY_SEC:-3}"

attempt=1
while (( attempt <= MAX_ATTEMPTS )); do
  echo "[recycle] attempt ${attempt}/${MAX_ATTEMPTS}: tearing down services..."
  if ! "$ROOT_DIR/ops/scripts/teardown_services.sh"; then
    echo "[recycle] teardown failed on attempt ${attempt}"
  else
    echo "[recycle] waiting 5 seconds..."
    sleep 5
    echo "[recycle] attempt ${attempt}/${MAX_ATTEMPTS}: standing up services..."
    if "$ROOT_DIR/ops/scripts/standup_services.sh"; then
      echo "[done] services recycle complete"
      exit 0
    fi
    echo "[recycle] standup failed on attempt ${attempt}"
  fi

  if (( attempt < MAX_ATTEMPTS )); then
    echo "[recycle] retrying in ${RETRY_DELAY_SEC}s..."
    sleep "$RETRY_DELAY_SEC"
  fi
  ((attempt += 1))
done

echo "[error] services recycle failed after ${MAX_ATTEMPTS} attempt(s)"
exit 1
