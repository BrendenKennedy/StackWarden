# CLI Architecture

## Role of the CLI

The CLI is the operator-focused orchestration surface for planning, building, inspecting, and governing artifacts. It prioritizes deterministic behavior, scriptability, and explicit failure semantics.

Primary entrypoints:

- Package entrypoint: `stacksmith = "stacksmith.cli_app:app"` in `pyproject.toml`
- CLI app definition and command wiring: `packages/stacksmith/src/stacksmith/cli.py`
- Shared setup and helpers: `packages/stacksmith/src/stacksmith/cli_shared/*`

## Command Model

The CLI combines top-level commands with grouped subcommands:

- Top-level examples: `plan`, `check`, `ensure`, `verify`, `inspect`, `compose`, `manifest`, `repro`, `sbom`, `doctor`, `init`, `wizard`
- Grouped surfaces: `list`, `profiles`, `stacks`, `blocks`, `catalog`, `export`, `migrate`

Risk taxonomy metadata is maintained in:

- `packages/stacksmith/src/stacksmith/cli_commands/low_risk.py`
- `packages/stacksmith/src/stacksmith/cli_commands/high_risk.py`

This helps operational framing and release review of command surfaces.

## Configuration and Environment Behavior

App configuration behavior is centralized in:

- `packages/stacksmith/src/stacksmith/config.py`
- `packages/stacksmith/src/stacksmith/paths.py`

Important conventions:

- Config file path defaults to XDG-compatible `~/.config/stacksmith/config.yaml`.
- Data roots default to XDG-compatible `~/.local/share/stacksmith`.
- `STACKSMITH_DATA_DIR` can override profile/stack/block roots.
- CLI context setup (`packages/stacksmith/src/stacksmith/cli_shared/context.py`) loads config and initializes logging.

Operational toggles include strict compatibility behavior, tuple layer mode, and remote catalog settings.

## Core Interaction Model

The CLI does not require API calls for core operations. It directly orchestrates shared domain/application modules, which means CLI and API behavior remain aligned through common core logic instead of duplicated implementations.

Key shared modules:

- `packages/stacksmith/src/stacksmith/application/create_flows.py`
- `packages/stacksmith/src/stacksmith/domain/ensure.py`
- `packages/stacksmith/src/stacksmith/resolvers/resolver.py`

Side-effectful interactions:

- Docker client wrappers in `packages/stacksmith/src/stacksmith/runtime/docker_client.py`
- Buildx subprocess integration in `packages/stacksmith/src/stacksmith/runtime/buildx.py`
- Build orchestration in `packages/stacksmith/src/stacksmith/builders/plan_executor.py`
- Catalog persistence in `packages/stacksmith/src/stacksmith/catalog/store.py`

## Error Handling and Exit Semantics

CLI error normalization and user-safe rendering are implemented in `packages/stacksmith/src/stacksmith/cli_shared/errors.py` and related helpers. The intent is stable machine/script behavior with predictable exit outcomes and actionable operator messaging.

## Design Decisions

- Shared-core orchestration avoids divergence between CLI and API behavior.
- Deterministic output (`--json` options, stable contract fields) supports automation pipelines.
- Wizard and create surfaces layer usability on top of the same deterministic core.
- Compatibility-first commands (`plan`, `check`) shift failures earlier in lifecycle.

## Testing Strategy for CLI

CLI coverage relies heavily on Typer `CliRunner` with environment and dependency patching.

Representative tests:

- `tests/test_cli_build_and_wizard.py`
- `tests/test_cli_entity_commands.py`
- `tests/test_cli_operations.py`
- `tests/test_cli_catalog.py`
- `tests/test_cli_parity.py`

Architecture guard tests also enforce layering boundaries:

- `tests/test_architecture_guards.py`

## Key Files to Read Next

- `packages/stacksmith/src/stacksmith/cli.py`
- `packages/stacksmith/src/stacksmith/cli_shared/context.py`
- `packages/stacksmith/src/stacksmith/cli_shared/errors.py`
- `packages/stacksmith/src/stacksmith/domain/ensure.py`
- `tests/test_cli_parity.py`

## Common Modification Scenarios

- Add a new command: add CLI handler, reuse core module behavior, add contract/CLI tests.
- Extend command output: preserve machine-consumable format stability for `--json`.
- Change configuration semantics: update config loaders and validate parity across CLI/API flows.
