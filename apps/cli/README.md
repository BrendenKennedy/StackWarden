# CLI App Surface

This directory exists as the CLI runtime surface in the `apps/` layout.

The canonical CLI implementation remains in the package at:

- `packages/stackwarden/src/stackwarden/cli.py`
- entrypoint script: `stackwarden` -> `stackwarden.cli_app:app`

Keeping CLI logic in the package preserves Python packaging conventions and keeps shared imports/tests straightforward, while this directory provides structural consistency with `apps/api` and `apps/web`.
