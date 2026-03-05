# Tools Policy

`tools/` is reserved for compatibility entrypoints and developer utilities.

Rules:

- Keep scripts thin; prefer delegating operational behavior to `ops/scripts/`.
- Do not add net-new operational orchestration logic directly in `tools/`.
- If an old command path must be preserved, keep the wrapper in `tools/` and point it to the canonical script in `ops/scripts/`.

If a script is required for runtime/deploy orchestration, place it in `ops/scripts/` first and only add a `tools/` wrapper when compatibility requires it.
