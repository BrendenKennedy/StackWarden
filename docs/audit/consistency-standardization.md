# Consistency And Standardization Rules

## Naming Standard

- Use `layer` terminology for user intent and feature units.
- Reserve `block` only for explicit backward-compatibility shims with deprecation notes.
- Keep endpoint group names and frontend API wrappers aligned (`profiles`, `stacks`, `layers`, `settings`, `jobs`, `meta`).

## Schema/Model Standard

- Canonical transport DTO definitions live in `packages/stackwarden/src/stackwarden/web/schemas.py`.
- Frontend mirrors in `apps/web/src/api/types.ts` should map fields 1:1 to transport contracts unless documented otherwise.
- `schema_version` policy must be explicit and entity-specific (profile/stack/layer), documented at API boundary.

## Error-Handling Standard

- Perform wire-format normalization at route and API-client boundaries.
- Keep domain/application exceptions transport-agnostic.
- Use explicit mapping (`ValidationError` -> DTO error list) at adapter boundaries.

## File and Function Size Guidance

- Trigger refactor review when files exceed ~800 lines or contain mixed concerns (validation + IO + mapping + orchestration).
- Current hotspots for decomposition:
  - `packages/stackwarden/src/stackwarden/cli.py`
  - `packages/stackwarden/src/stackwarden/web/schemas.py`
  - `apps/web/src/components/BlockWizardModal.vue`
  - `apps/web/src/views/SettingsView.vue`

## Tooling Consistency

- Python style: `ruff check`, `ruff format`, `mypy` (as configured in `Makefile`/`pyproject.toml`).
- Frontend: `vue-tsc` and `vitest` are present; linting policy should be made explicit in a follow-up gate.

## Enforcement Hooks

- Contract sync guard: `tests/test_contract_sync.py`
- Architecture guards: `tests/test_architecture_guards.py`
- Legacy alias containment: `tests/test_legacy_alias_boundaries.py`
- Static bundle hygiene guard: `tests/web/test_static_assets_hygiene.py`
- Legacy route deprecation helper tests: `apps/web/tests/route-deprecations.spec.ts`
- CI baseline: `.github/workflows/ci.yml`
