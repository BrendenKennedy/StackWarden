# CLI Architecture

## Role of the CLI

The CLI is the operator-focused orchestration surface for planning, building, inspecting, and governing artifacts. It prioritizes deterministic behavior, scriptability, and explicit failure semantics.

Primary entrypoints:

- Package entrypoint: `stackwarden = "stackwarden.cli_app:app"` in `pyproject.toml`
- CLI app definition and command wiring: `packages/stackwarden/src/stackwarden/cli.py`
- Shared setup and helpers: `packages/stackwarden/src/stackwarden/cli_shared/*`

## Command Model

The CLI combines top-level commands with grouped subcommands:

- Top-level examples: `plan`, `check`, `ensure`, `verify`, `inspect`, `inspect-layer`, `compose`, `manifest`, `repro`, `sbom`, `doctor`, `init`, `wizard`
- Grouped surfaces: `list`, `profiles`, `stacks`, `layers`, `catalog`, `export`, `migrate`

Entity-specific list commands (for example `stackwarden profiles list`) are maintained as compatibility aliases with deprecation guidance toward `stackwarden list ...`.

Risk taxonomy metadata is maintained in:

- `packages/stackwarden/src/stackwarden/cli_commands/low_risk.py`
- `packages/stackwarden/src/stackwarden/cli_commands/high_risk.py`

This helps operational framing and release review of command surfaces.

## Configuration and Environment Behavior

App configuration behavior is centralized in:

- `packages/stackwarden/src/stackwarden/config.py`
- `packages/stackwarden/src/stackwarden/paths.py`

Important conventions:

- Config file path defaults to XDG-compatible `~/.config/stackwarden/config.yaml`.
- Data roots default to XDG-compatible `~/.local/share/stackwarden`.
- `STACKWARDEN_DATA_DIR` can override profile/stack/layer roots.
- CLI context setup (`packages/stackwarden/src/stackwarden/cli_shared/context.py`) loads config and initializes logging.

Operational toggles include strict compatibility behavior, tuple layer mode, and remote catalog settings.

## Core Interaction Model

The CLI does not require API calls for core operations. It directly orchestrates shared domain/application modules, which means CLI and API behavior remain aligned through common core logic instead of duplicated implementations.

Key shared modules:

- `packages/stackwarden/src/stackwarden/application/create_flows.py`
- `packages/stackwarden/src/stackwarden/domain/ensure.py`
- `packages/stackwarden/src/stackwarden/resolvers/resolver.py`

Side-effectful interactions:

- Docker client wrappers in `packages/stackwarden/src/stackwarden/runtime/docker_client.py`
- Buildx subprocess integration in `packages/stackwarden/src/stackwarden/runtime/buildx.py`
- Build orchestration in `packages/stackwarden/src/stackwarden/builders/plan_executor.py`
- Catalog persistence in `packages/stackwarden/src/stackwarden/catalog/store.py`

## Error Handling and Exit Semantics

CLI error normalization and user-safe rendering are implemented in `packages/stackwarden/src/stackwarden/cli_shared/errors.py` and related helpers. The intent is stable machine/script behavior with predictable exit outcomes and actionable operator messaging.

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

- `packages/stackwarden/src/stackwarden/cli.py`
- `packages/stackwarden/src/stackwarden/cli_shared/context.py`
- `packages/stackwarden/src/stackwarden/cli_shared/errors.py`
- `packages/stackwarden/src/stackwarden/domain/ensure.py`
- `tests/test_cli_parity.py`

## Common Modification Scenarios

- Add a new command: add CLI handler, reuse core module behavior, add contract/CLI tests.
- Extend command output: preserve machine-consumable format stability for `--json`.
- Change configuration semantics: update config loaders and validate parity across CLI/API flows.
