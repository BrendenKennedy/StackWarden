# CLI Production Review

## Scope Inventory

- Entrypoints: `/stacksmith/cli_app.py`, `/stacksmith/cli.py`
- Command safety maps: `/stacksmith/cli_commands/high_risk.py`, `/stacksmith/cli_commands/low_risk.py`
- CLI shared helpers: `/stacksmith/cli_shared/context.py`, `/stacksmith/cli_shared/errors.py`, `/stacksmith/cli_shared/catalog.py`
- Wizard surface: `/stacksmith/ui/wizard.py`
- Runtime paths exercised from CLI: `/stacksmith/domain/ensure.py`, `/stacksmith/domain/remote_catalog.py`, `/stacksmith/runtime/buildx.py`, `/stacksmith/catalog/store.py`

## CLI vs Core/Web Parity Matrix

| Area | Previous CLI Behavior | Core/Web Behavior | Change |
| --- | --- | --- | --- |
| Strict compatibility default (`plan`) | Non-strict by default | Uses `STACKSMITH_COMPAT_STRICT` default in ensure/web | `plan` now passes `compatibility_strict_default()` into `resolve()` |
| Strict compatibility default (`check`) | Defaulted to `False` unless `--strict` | Env-driven strict default available in core/web | `check` now defaults from `STACKSMITH_COMPAT_STRICT` and supports `--strict/--no-strict` override |
| Wizard preview strictness | Preview resolve was non-strict | Ensure execution path uses strict env default | Wizard preview and CLI wizard rendering now use strict default |
| Repro plan strictness | Repro resolve was non-strict | Core ensure path uses strict env default | Repro resolve now uses strict default |
| Export runtime behavior | Assumed NVIDIA + GPUs | Profiles can be `runc`/CPU only | Export commands now derive runtime from artifact/profile and only emit GPU flags/reservations for NVIDIA runtime |
| Exit-code semantics | Some exception paths forced exit code `1` | Domain errors define explicit exit codes | Exception handlers in key commands now route through `_exit_code_for()` |

## Reliability and Performance Hardening

- Remote catalog git operations now have bounded timeout via `STACKSMITH_REMOTE_GIT_TIMEOUT` (default `30s`).
- `ensure_internal()` now degrades gracefully when remote catalog sync fails (warn + continue with local data).
- Buildx execution now streams logs during build instead of waiting for full buffered output.
- SQLite catalog engine now configures:
  - connection timeout,
  - `WAL` journal mode,
  - `synchronous=NORMAL`,
  - `busy_timeout`,
  - retry-on-lock commit behavior for write operations.
- CLI list commands now batch origin metadata lookups to avoid repeated config reloads per item.
- `catalog disk-usage` now memoizes repeated image inspections and reports inspect failures.
- `prune` now reports and logs image removal failures instead of silently swallowing errors.

## Test Additions

- `tests/test_cli_parity.py`
  - Validates strict default parity for `plan`.
  - Validates env default + override behavior for `check`.
- `tests/test_cli_exports.py`
  - Validates CPU runtime export omits default GPU flags.
  - Validates NVIDIA runtime export still includes GPU defaults.
- `tests/test_ensure_registry_enforcement.py`
  - Adds coverage for remote sync failure degraded behavior in `ensure_internal`.
- `tests/test_buildx.py`
  - Updated for streaming execution implementation.
- `tests/test_web_entrypoint.py`
  - Verifies actionable error when web extras are missing.

## Production Release Gates (CLI)

- Compatibility behavior is consistent across `check`, `plan`, `wizard`, and `ensure`.
- External command paths (`git`, `buildx`) are bounded and observable.
- Catalog persistence is resilient under lock contention.
- CLI error exits are deterministic for domain-level failures.
- Exported run/compose helpers remain valid for both GPU and CPU profiles.
