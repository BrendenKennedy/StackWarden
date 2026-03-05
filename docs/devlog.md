# Stacksmith Devlog — Stress Test Bug Tracking

This devlog records bugs and issues discovered during stress testing. Add entries as tests are run and issues are found.

## Format

Each entry should include:

- **Date**: When the bug was found
- **Test**: Which stress test or scenario
- **Severity**: `critical` | `high` | `medium` | `low` | `info`
- **Status**: `open` | `fixed` | `wontfix` | `duplicate`
- **Description**: What happened
- **Expected**: What should have happened
- **Notes**: Reproducer, workaround, or follow-up

---

## Entries

<!-- Add entries below as bugs are found during stress testing -->

### 2025-03-04 — Stress test suite created

- **Test**: N/A (initial setup)
- **Severity**: info
- **Status**: N/A
- **Description**: Stress test suite and devlog created. Tests cover: concurrency, fingerprint determinism, compatibility-fix retry, resource/network failure, schema/malformed input, wheelhouse/npm, cross-platform, catalog lifecycle, CLI edge cases.
- **Expected**: N/A
- **Notes**: Run `pytest tests/test_stress_*.py -v` or `./ops/scripts/stress_builds.sh` to execute stress tests. Use `--devlog` to append failures to this file.

---
