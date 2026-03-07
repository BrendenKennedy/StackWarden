# Legacy And Orphan Analysis (Blocks -> Layers)

## Objective

Identify and control leftover `block` references during the transition to layers-first terminology and workflows.

## Evidence Snapshot

- Frontend still contains block-named UX surfaces:
  - `apps/web/src/views/BlocksView.vue`
  - `apps/web/src/components/BlockCreateFlowModal.vue`
  - `apps/web/src/composables/useBlockCreateFlow.ts`
- Router retains compatibility redirects:
  - `apps/web/src/router.ts` for `/blocks` paths redirecting to `/layers`
- Backend aliases and naming residue:
  - `packages/stackwarden/src/stackwarden/application/create_flows.py`: deprecated `create_block(...)` wrapper delegates to `create_layer(...)`
  - `packages/stackwarden/src/stackwarden/catalog/*`: `block_schema_version` persistence fields
  - `packages/stackwarden/src/stackwarden/domain/drift.py`: `stackwarden.block_schema_version` label checks

## Classification

- **Intentional compatibility residue:** redirect routes, alias shim
- **Migration residue requiring rename plan:** persistence field/label names
- **Potential orphan risk:** any new `block*` symbols introduced outside allowlisted migration paths

## Deprecation Decisions

1. Keep `/blocks` redirects in this pass to avoid breaking bookmarks/incoming links, with removal scheduled after `2026-12-31`.
2. Keep `create_block`/`run_block_create_wizard` aliases only as temporary compatibility shims, with removal scheduled after `2026-06-30`.
3. Do not rename persistence fields in this pass (requires safe data migration and compatibility strategy).

## Controls Added In This Pass

- Added architecture guard to prevent non-web `stackwarden.web.schemas` import spread:
  - `tests/test_architecture_guards.py::test_only_allowlisted_modules_import_web_schemas`
- Added alias-boundary guard to prevent new block-era helper usage beyond compatibility shims:
  - `tests/test_legacy_alias_boundaries.py::test_legacy_block_alias_usage_is_contained`
- Added explicit frontend deprecation marker for legacy `/blocks` routes:
  - `apps/web/src/routerDeprecations.ts` and `apps/web/src/router.ts` (warn once when navigation is redirected from `/blocks*`)
- This helps contain migration debt while refactoring proceeds in bounded PRs.

## Recommended Next PRs

- **PR-L1:** Move block-named frontend component/composable file names to layer naming while preserving route compatibility.
- **PR-L2:** Introduce storage migration plan from `block_schema_version` to `layer_schema_version` with backward compatibility read path.
- **PR-L3:** Remove `create_block` alias after downstream CLI/API callers are confirmed migrated.
