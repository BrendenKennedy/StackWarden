# Architecture Boundary And Uniformity Audit

## Boundary Rule

Internal layers (`domain`, `application`, CLI adapters, UI wizard entities) should not directly depend on transport-only DTO modules unless explicitly allowlisted during migration.

## Current Findings

### AUD-005 (S1): Internal modules import transport DTOs

- `packages/stackwarden/src/stackwarden/application/create_flows.py`
- `packages/stackwarden/src/stackwarden/ui/wizard_entities/profile.py`
- `packages/stackwarden/src/stackwarden/ui/wizard_entities/stack.py`
- `packages/stackwarden/src/stackwarden/ui/wizard_entities/block.py`
- `packages/stackwarden/src/stackwarden/cli.py`

This causes coupling where API DTO evolution can unintentionally drive internal model shape decisions.

## Standardization Rules (Adopted)

1. `web/schemas.py` is transport boundary only.
2. Internal workflows should prefer domain or application-local input models.
3. Cross-boundary conversion happens in mapper functions at adapter boundaries.
4. New imports of `stackwarden.web.schemas` outside web routes/services are blocked unless allowlisted.

## Control Implemented In This Pass

- `tests/test_architecture_guards.py` now includes:
  - `test_only_allowlisted_modules_import_web_schemas`

This prevents spread of the coupling while staged refactors remove existing allowlisted imports.

## Mapper Pattern Target (for next remediation PR)

- `route DTO -> app request model -> domain model -> response DTO`
- Keep normalization logic centralized in application mapping functions.
- Keep error translation at route/CLI adapters, not inside domain logic.
