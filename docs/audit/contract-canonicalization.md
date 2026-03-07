# Contract And Schema Canonicalization

## Canonical Source Decision

- **Canonical transport contract source:** `packages/stackwarden/src/stackwarden/web/schemas.py`
- **Canonical frontend constants source:** `stackwarden.contracts.constants` generated into `apps/web/src/api/contracts.generated.ts`
- **Frontend usage rule:** `apps/web/src/api/types.ts` and `apps/web/src/api/endpoints.ts` must mirror backend transport DTO and route shape; these are consumer-facing mirrors, not authoritative contract definitions.

## Evidence Summary

- API DTOs are centralized in `web/schemas.py` and used by route `response_model` definitions.
- Existing contract sync coverage exists in `tests/test_contract_sync.py`.
- Endpoint wrappers are centralized in `apps/web/src/api/endpoints.ts`.
- Type mirrors are centralized in `apps/web/src/api/types.ts`.

## Drift Findings

### AUD-001 (S1): Schema version signaling is inconsistent across create payload producers

- **Locations:** `apps/web/src/composables/useProfileCreateFlow.ts`, `apps/web/src/composables/useStackCreateFlow.ts`, `apps/web/src/composables/useBlockCreateFlow.ts`, `packages/stackwarden/src/stackwarden/web/schemas.py`
- **Evidence:** profile/stack payload builders send `schema_version: 3`, layer payloads send `schema_version: 2`, while backend create DTO defaults remain `schema_version: 1`.
- **Risk:** readers and external API clients cannot infer canonical version intent from transport defaults; drift can silently accumulate.
- **Decision:** keep behavior unchanged in this pass; track as bounded follow-up with explicit schema version policy and migration note.

### AUD-002 (S2): Frontend endpoint drift checks were too narrow

- **Locations:** `tests/test_contract_sync.py`
- **Evidence:** prior assertions covered only minimal endpoint examples.
- **Risk:** route shape changes can slip through without early signal.
- **Remediation in this pass:** expanded sync assertions for create-contract versioning, tuple catalog endpoint, and layer-option classification endpoint.

## Remediation Applied

- Updated `tests/test_contract_sync.py` to widen endpoint-shape parity checks.
- Preserved runtime behavior to avoid introducing transport-breaking changes during audit pass.

## Follow-up Actions

1. Define and document a single supported `schema_version` policy per entity (`profile`, `stack`, `layer`) in API docs and DTO defaults.
2. Add API contract snapshot generation/check in CI for broader route+DTO drift detection.
