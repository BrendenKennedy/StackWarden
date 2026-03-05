#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[Milestone A] Domain/CLI"
pytest -q \
  "$ROOT_DIR/tests/test_resolver.py" \
  "$ROOT_DIR/tests/test_hardware_catalog.py" \
  "$ROOT_DIR/tests/test_compatibility_rules.py" \
  "$ROOT_DIR/tests/test_cli_entity_commands.py"

echo "[Milestone B] API"
pytest -q \
  "$ROOT_DIR/tests/web/test_entity_api.py" \
  "$ROOT_DIR/tests/web/test_profiles_resilience.py" \
  "$ROOT_DIR/tests/web/test_settings_catalog.py" \
  "$ROOT_DIR/tests/web/test_system_meta.py" \
  "$ROOT_DIR/tests/web/test_compatibility_api.py"

echo "[Milestone C] UI"
(
  cd "$ROOT_DIR/apps/web"
  npm test
)

echo "[Milestone D] E2E smoke"
pytest -q \
  "$ROOT_DIR/tests/test_build_integration.py" \
  "$ROOT_DIR/tests/test_immutable.py"

echo "All milestone gates passed."
