# CLI Wizard Usage

Stacksmith now supports guided create flows for profiles, blocks, and stacks.

## Commands

- `stacksmith profiles wizard`
- `stacksmith blocks wizard`
- `stacksmith stacks wizard`

## Common Flags

- `--non-interactive`: run with defaults/overrides only (CI friendly).
- `--dry-run`: validate and render YAML without writing.
- `--yes`: skip confirmation and write immediately.
- `--output <path>`: write preview YAML to a file.
- `--json`: return machine-readable wizard result.

## Block Wizard Extras

- `--preset <id>`
- `--profile-mode base|cpu|gpu|dev|prod`
- `--requirements-file <path>`
- `--package-json-file <path>`
- `--apt-file <path>`

## Stack Wizard Notes

- Build strategy is a dedicated decision step and is not part of layer selection.
- `system_runtime_layer` is required for successful stack composition.
- Compose preview runs before create to surface conflicts.

## Manual Edit Fallback

Power users can still use:

- `stacksmith profiles create --file ...`
- `stacksmith blocks create --file ...`
- `stacksmith stacks create --file ...`

Run `--dry-run` and `doctor` for validation/health checks before writing in CI.
