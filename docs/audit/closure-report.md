# Audit Closure Report (Pass 1)

## Scope

- `apps/web`
- `packages/stackwarden`
- `specs`

## What Was Completed

- Baseline controls and pass/fail criteria established in `docs/audit/baseline-checklist.md`.
- Findings register created with severity and status in `docs/audit/findings-register.md`.
- Contract/source-of-truth decision documented in `docs/audit/contract-canonicalization.md`.
- Legacy/orphan analysis and deprecation decisions documented in `docs/audit/legacy-orphan-analysis.md`.
- Boundary/uniformity controls documented in `docs/audit/boundary-uniformity.md`.
- Consistency standards documented in `docs/audit/consistency-standardization.md`.
- Remediation sequencing documented in `docs/audit/remediation-roadmap.md`.
- Issue/PR templates added for execution consistency.

## Code Changes Applied

- `tests/test_contract_sync.py`
  - Expanded endpoint-shape checks.
  - Added schema-version contract assertions for `v1`/`v2`/`v3`.
  - Added guard to prevent `/blocks` endpoint regressions in frontend API wrappers.
  - Updated runtime endpoint test to authenticate via `/api/auth/setup` before protected `/api/jobs/*` call.
- `tests/test_architecture_guards.py`
  - Added non-web allowlist guard for `stackwarden.web.schemas` imports and tightened allowlist.
- `tests/test_legacy_alias_boundaries.py`
  - Added containment guard to ensure block-era alias symbols do not spread beyond approved compatibility files.
- `packages/stackwarden/src/stackwarden/application/create_flows.py`
  - Replaced block alias assignments with explicit deprecation wrapper functions and warning emissions.
  - Added `validate_*_create_request(...)` helpers to centralize transport request validation.
- `packages/stackwarden/src/stackwarden/ui/wizard_entities/block.py`
- `packages/stackwarden/src/stackwarden/ui/wizard_entities/profile.py`
- `packages/stackwarden/src/stackwarden/ui/wizard_entities/stack.py`
- `packages/stackwarden/src/stackwarden/cli.py`
  - Removed direct `stackwarden.web.schemas` imports from CLI and wizard entities by routing payload validation through application helpers.
  - Promoted `run_layer_create_wizard` as primary API and kept `run_block_create_wizard` as deprecated wrapper.
- `packages/stackwarden/src/stackwarden/application/create_flows.py`
- `docs/audit/legacy-orphan-analysis.md`
  - Added explicit alias deprecation schedule (`remove after 2026-06-30`) and enforced warning-message consistency in tests.
- `packages/stackwarden/src/stackwarden/domain/errors.py`
  - Added temporary `BlockNotFoundError` compatibility alias to `LayerNotFoundError`.
- `packages/stackwarden/src/stackwarden/web/routes/meta.py`
  - Added per-entity `defaults.schema_version` contract defaults for profile/stack/layer.
- `packages/stackwarden/src/stackwarden/contracts/constants.py`
- `packages/stackwarden/src/stackwarden/contracts/__init__.py`
- `packages/stackwarden/src/stackwarden/application/create_request_models.py`
- `packages/stackwarden/src/stackwarden/web/schemas.py`
  - Added shared create schema-version defaults and aligned application/web request model defaults with current layer-first policy.
- `packages/stackwarden/src/stackwarden/catalog/models.py`
- `packages/stackwarden/src/stackwarden/catalog/migrations.py`
- `packages/stackwarden/src/stackwarden/catalog/store.py`
- `packages/stackwarden/src/stackwarden/builders/plan_executor.py`
- `packages/stackwarden/src/stackwarden/domain/drift.py`
- `packages/stackwarden/src/stackwarden/resolvers/resolver.py`
  - Added backward-compatible `layer_schema_version` migration path while preserving `block_schema_version` fallback for existing rows/labels.
  - Normalized internal layer-schema handling with explicit compatibility fallback helpers and drift checks.
- `tests/test_catalog_migrations.py`
- `tests/test_catalog.py`
  - Added migration/store regression coverage to verify backfill from `block_schema_version` and runtime fallback behavior when migrated rows carry default layer values.
- `apps/web/src/api/schemaVersions.ts`
  - Added centralized create schema-version policy and contract-aware resolution helper.
- `apps/web/src/composables/useProfileCreateFlow.ts`
- `apps/web/src/composables/useStackCreateFlow.ts`
- `apps/web/src/composables/useBlockCreateFlow.ts`
  - Switched to `resolveCreateSchemaVersion(...)` so runtime payload versions follow backend contract metadata.
- `apps/web/src/components/LayerCreateFlowModal.vue`
- `apps/web/src/components/LayerWizardModal.vue`
- `apps/web/src/composables/useLayerCreateFlow.ts`
- `apps/web/src/views/LayersView.vue`
  - Added layer-first component/composable/view entrypoints while preserving compatibility wrappers.
- `apps/web/src/views/BlocksView.vue`
- `apps/web/src/router.ts`
- `apps/web/src/routerDeprecations.ts`
- `apps/web/tests/block-wizard.spec.ts`
- `apps/web/tests/blocks-view-modal.spec.ts`
- `apps/web/tests/profile-wizard.spec.ts`
- `apps/web/tests/route-deprecations.spec.ts`
  - Updated first-party imports/tests to layer-first naming and route usage.
  - Added explicit `/blocks*` deprecation warning path with scheduled removal date for compatibility redirects.
- `tests/web/test_static_assets_hygiene.py`
  - Added packaged-static hygiene gate to ensure `index.html` references existing hashed entry assets and stale `index-*` bundles are not retained.
- `apps/web/tests/schema-versions.spec.ts`
- `tests/test_create_flow_compat_aliases.py`
- `tests/test_create_wizard_entities.py`
- `tests/web/test_system_meta.py`
  - Added focused regression coverage for schema versions and deprecation compatibility.

## Verification Evidence

- `pytest tests/test_contract_sync.py tests/web/test_system_meta.py tests/test_create_flow_compat_aliases.py tests/test_create_wizard_entities.py tests/test_architecture_guards.py -q`
  - Result: `22 passed`
- `pytest tests/test_architecture_guards.py tests/test_create_wizard_entities.py tests/test_cli_entity_commands.py tests/test_cli_create_wizards.py -q`
  - Result: `15 passed`
- `pytest tests/test_architecture_guards.py tests/test_create_wizard_entities.py tests/test_cli_entity_commands.py tests/test_cli_create_wizards.py tests/test_contract_sync.py tests/web/test_system_meta.py -q`
  - Result: `26 passed`
- `pytest tests/test_create_flow_compat_aliases.py tests/test_create_wizard_entities.py tests/test_architecture_guards.py tests/test_cli_create_wizards.py -q`
  - Result: `15 passed`
- `pytest tests/test_legacy_alias_boundaries.py tests/test_create_flow_compat_aliases.py tests/test_create_wizard_entities.py -q`
  - Result: `9 passed`
- `pytest tests/test_catalog_migrations.py tests/test_catalog.py -q`
  - Result: `21 passed`
- `pytest tests/test_drift.py tests/test_catalog.py tests/test_immutable.py tests/web/test_jobs_plan_verify_artifacts.py -q`
  - Result: `35 passed`
- `pytest tests/test_resolver.py tests/test_drift.py tests/test_catalog.py -q`
  - Result: `53 passed`
- `pytest tests/test_drift.py tests/test_catalog.py tests/test_resolver.py tests/test_immutable.py tests/web/test_jobs_plan_verify_artifacts.py -q`
  - Result: `67 passed`
- `pytest tests/test_contract_sync.py tests/web/test_system_meta.py tests/web/test_create.py tests/test_architecture_guards.py -q`
  - Result: `63 passed`
- `npm run test --prefix apps/web -- tests/schema-versions.spec.ts tests/block-wizard.spec.ts tests/blocks-view-modal.spec.ts tests/profile-wizard.spec.ts`
  - Result: `14 passed`
- `npm run test --prefix apps/web -- tests/route-deprecations.spec.ts`
  - Result: `2 passed`
- `pytest tests/web/test_static_assets_hygiene.py -q`
  - Result: `2 passed`
- `ruff check` on touched Python files (excluding pre-existing repository-level `cli.py` lint debt)
  - Result: `All checks passed`

## Residual Risk Backlog (Owner Assigned)

- `AUD-001` (S1): schema-version policy drift (`Owner: API + UI`) - resolved
- `AUD-004` (S1): persistence naming migration (`block_schema_version`) (`Owner: Core + Catalog`) - resolved
- `AUD-005` (S1): internal transport DTO coupling (`Owner: Core`) - resolved
- `AUD-003` (S1): compatibility alias lifecycle (`Owner: Core`) - resolved
- `AUD-007` (S2): `/blocks` redirect deprecation timeline (`Owner: UI`) - resolved
- `AUD-008` (S2): static asset hygiene in package tree (`Owner: UI + Release`) - resolved

## Sign-off Checklist

- [x] Audit artifacts created and linked
- [x] Severity rubric applied
- [x] Owner-tagged backlog published
- [x] Targeted quality gates executed
- [x] All S1 items remediated in this pass
