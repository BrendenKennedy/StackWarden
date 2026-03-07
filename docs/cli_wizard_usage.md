# CLI Wizard Usage

Use CLI wizards when you want guided create flows with validation and optional non-interactive execution.

## Commands

- `stackwarden profiles wizard`
- `stackwarden layers wizard`
- `stackwarden stacks wizard`

## Common Flags

- `--non-interactive`: run with defaults/overrides only (CI friendly).
- `--dry-run`: validate and render YAML without writing.
- `--yes`: skip confirmation and write immediately.
- `--output <path>`: write preview YAML to a file.
- `--json`: return machine-readable wizard result.

## Layer Wizard Extras

- `--preset <id>`
- `--profile-mode base|cpu|gpu|dev|prod`
- `--requirements-file <path>`
- `--package-json-file <path>`
- `--apt-file <path>`

## Stack Wizard Notes

- Build strategy is a dedicated decision step (separate from layer selection).
- `system_runtime_layer` is required for successful stack composition.
- Compose preview runs before create to surface conflicts.
- Layer options are compatibility-aware and grouped by recommendation status.

## Manual Edit Fallback

Power users can use file-based create flows:

- `stackwarden profiles create --file ...`
- `stackwarden layers create --file ...`
- `stackwarden stacks create --file ...`

Run `--dry-run` and `doctor` for validation/health checks before writing in CI.
