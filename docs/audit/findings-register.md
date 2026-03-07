# Findings Register

## Scoring

- Severity: S0 critical, S1 high, S2 medium, S3 low
- Priority score: `Severity x BlastRadius x Confidence - RemediationCostModifier`

## Findings

| ID | Category | Severity | Location | Risk | Recommended Fix | Owner | Status |
|---|---|---|---|---|---|---|---|
| AUD-001 | schema/model drift | S1 | `apps/web/src/composables/useProfileCreateFlow.ts`, `apps/web/src/composables/useStackCreateFlow.ts`, `apps/web/src/composables/useBlockCreateFlow.ts`, `apps/web/src/api/schemaVersions.ts`, `packages/stackwarden/src/stackwarden/contracts/constants.py`, `packages/stackwarden/src/stackwarden/application/create_request_models.py`, `packages/stackwarden/src/stackwarden/web/routes/meta.py`, `packages/stackwarden/src/stackwarden/web/schemas.py` | Confusing schema-version contract behavior and future drift | Define per-entity schema-version policy in shared constants and align request-model defaults + contract metadata | API + UI | resolved |
| AUD-002 | contract sync coverage gap | S2 | `tests/test_contract_sync.py` | Silent frontend endpoint drift | Expand contract sync assertions for key endpoint signatures | API + UI | resolved |
| AUD-003 | legacy alias/deprecation | S1 | `packages/stackwarden/src/stackwarden/application/create_flows.py`, `packages/stackwarden/src/stackwarden/ui/wizard_entities/block.py` | Ambiguous code paths and transition debt | Keep alias temporarily, enforce explicit deprecation schedule and guard against spread | Core | resolved |
| AUD-004 | legacy naming persistence | S1 | `packages/stackwarden/src/stackwarden/catalog/store.py`, `packages/stackwarden/src/stackwarden/catalog/models.py`, `packages/stackwarden/src/stackwarden/catalog/migrations.py`, `packages/stackwarden/src/stackwarden/builders/plan_executor.py`, `packages/stackwarden/src/stackwarden/domain/drift.py` (`block_schema_version` compatibility path) | Mixed block/layer terminology across persistence and labels | Introduce backward-compatible `layer_schema_version` read/write path and keep `block_schema_version` fallback during migration window | Core + Catalog | resolved |
| AUD-005 | architecture boundary leak | S1 | previously `packages/stackwarden/src/stackwarden/application/create_flows.py`, `packages/stackwarden/src/stackwarden/ui/wizard_entities/*.py`, and `packages/stackwarden/src/stackwarden/cli.py` | Transport DTO leakage entangles core evolution with web DTO churn | Application-owned request models and centralized validators; enforce no non-web `web.schemas` imports via architecture guards | Core | resolved |
| AUD-006 | architecture guard coverage gap | S2 | `tests/test_architecture_guards.py` | New boundary leaks can spread silently | Add allowlist guard for non-web imports of `stackwarden.web.schemas` | Core | resolved |
| AUD-007 | route legacy surface | S2 | `apps/web/src/router.ts` (`/blocks` redirects), `apps/web/src/views/LayersView.vue`, `apps/web/src/components/LayerCreateFlowModal.vue`, `apps/web/src/components/LayerWizardModal.vue` | Legacy routes retained without deprecation timeline | Keep redirects for compatibility while converting first-party UI and tests to layer-first names | UI | resolved |
| AUD-008 | artifact hygiene risk | S2 | `packages/stackwarden/src/stackwarden/web/static/assets` | Hashed static bundles in package tree can accumulate stale assets | Enforce asset generation/cleanup policy and gate stale artifact retention | UI + Release | resolved |

## Notes

- `accepted-risk` means intentionally deferred with explicit follow-up action.
- This register is the source for remediation tickets and PR batches.
