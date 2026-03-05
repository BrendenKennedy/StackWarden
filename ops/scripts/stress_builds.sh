#!/usr/bin/env bash
# Stress test runner for StackWarden.
# Runs all test_stress_*.py tests and optionally appends results to docs/devlog.md.
#
# Usage:
#   ./ops/scripts/stress_builds.sh           # Run stress tests
#   ./ops/scripts/stress_builds.sh --devlog  # Run and append failures to devlog

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

STRESS_TESTS="tests/test_stress_*.py"
DEVLOG="${REPO_ROOT}/docs/devlog.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

run_stress_tests() {
    echo "=== StackWarden Stress Tests ==="
    echo "Timestamp: $TIMESTAMP"
    echo "Tests: $STRESS_TESTS"
    echo ""
    python -m pytest $STRESS_TESTS -v --tb=short 2>&1
}

append_failures_to_devlog() {
    local output_file="$1"
    local exit_code="$2"
    if [[ $exit_code -ne 0 ]] && [[ -f "$output_file" ]]; then
        echo ""
        echo "---" >> "$DEVLOG"
        echo ""
        echo "### $TIMESTAMP — Stress run failures" >> "$DEVLOG"
        echo "" >> "$DEVLOG"
        echo "- **Test**: \`pytest $STRESS_TESTS\`" >> "$DEVLOG"
        echo "- **Severity**: info" >> "$DEVLOG"
        echo "- **Status**: open" >> "$DEVLOG"
        echo "- **Description**: Stress test run reported failures. See output below." >> "$DEVLOG"
        echo "- **Expected**: All stress tests pass." >> "$DEVLOG"
        echo "- **Notes**: Run \`pytest $STRESS_TESTS -v\` to reproduce." >> "$DEVLOG"
        echo "" >> "$DEVLOG"
        echo '```' >> "$DEVLOG"
        tail -n 100 "$output_file" >> "$DEVLOG"
        echo '```' >> "$DEVLOG"
        echo "" >> "$DEVLOG"
        echo "Appended failure summary to $DEVLOG"
    fi
}

main() {
    if [[ "${1:-}" == "--devlog" ]]; then
        OUTPUT=$(mktemp)
        EXIT=0
        run_stress_tests > "$OUTPUT" 2>&1 || EXIT=$?
        cat "$OUTPUT"
        append_failures_to_devlog "$OUTPUT" "$EXIT"
        rm -f "$OUTPUT"
        exit $EXIT
    else
        run_stress_tests
    fi
}

main "$@"
