# Design Decisions and ADRs

## Decision Log Purpose

This page consolidates major StackWarden design choices and links rationale to implementation boundaries. It complements formal ADRs and provides practical context for contributors making architecture-impacting changes.

Primary ADR reference:

- `docs/adr/intent-first-contract.md`

## Major Decisions

## 1) Blocks-First Intent Contract

Decision:

- Treat ordered stack blocks as the primary authored intent surface.

Why:

- Keeps user goals explicit and composable.
- Avoids burying intent in host-specific configuration.

Trade-off:

- Requires stronger composition and conflict semantics.

Where enforced:

- Stack/block composition and resolver compatibility layers.

## 2) Shared Core for CLI and API

Decision:

- CLI and API are orchestration shells over common domain/application logic.

Why:

- Reduces behavior drift between interfaces.
- Enables consistent testable semantics independent of transport.

Trade-off:

- Requires disciplined layering and architecture guard tests.

Where enforced:

- Shared use of `packages/stackwarden/src/stackwarden/domain/ensure.py`, resolver modules, and create flows.

## 3) Resolver Purity Boundary

Decision:

- Keep resolver deterministic and side-effect free.

Why:

- Improves reproducibility and test confidence.
- Simplifies analysis of compatibility and planning regressions.

Trade-off:

- Requires careful boundary management when adding features that might tempt side effects.

Where enforced:

- `packages/stackwarden/src/stackwarden/resolvers/*` module responsibilities and architecture tests.

## 4) Deterministic Fingerprinting and Provenance

Decision:

- Artifact identity derives from deterministic fingerprint inputs plus provenance labels/manifest data.

Why:

- Supports reproducible builds, drift detection, and forensic traceability.

Trade-off:

- Changes to fingerprint inputs can cause broad tag churn and migration considerations.

Where enforced:

- Domain fingerprinting, ensure flows, manifest capture, catalog lifecycle behavior.

## 5) Compatibility-First Failure Model

Decision:

- Prefer preflight compatibility failures over late runtime failures.

Why:

- Saves build time and improves operator confidence.

Trade-off:

- More up-front validation complexity and maintenance of rule catalogs.

Where enforced:

- Resolver compatibility checks, rule catalogs, and preview endpoints/commands.

## 6) API Security by Token Gate

Decision:

- Use bearer token auth for API perimeter and admin token for privileged mutation paths.

Why:

- Lightweight operational security aligned to local/single-tenant deployment expectations.

Trade-off:

- Not a full identity/RBAC system; deployments needing multi-tenant policy need additional controls.

Where enforced:

- API middleware and privileged route checks.

## 7) Modal/Wizard UX with Explicit Write Confirmation

Decision:

- Use guided create flows with dry-run and confirm-write semantics in Web UI.

Why:

- Reduces accidental writes and clarifies what will be persisted.

Trade-off:

- More UX flow complexity compared to direct-form save patterns.

Where enforced:

- Frontend create flow composables, wizard modals, create/dry-run API routes.

## Architectural Trade-Off Matrix

| Decision | Benefit | Cost | If You Change It |
| --- | --- | --- | --- |
| Blocks-first contract | clear user intent | stricter composition model | update schemas, resolver rules, and docs together |
| Shared core across surfaces | parity and lower drift | layering discipline required | run parity and architecture guard tests |
| Resolver purity | deterministic planning | boundaries must be guarded | isolate side effects to runtime/builders |
| Compatibility-first checks | fail early, safer ops | rule maintenance overhead | update rule catalogs and compatibility tests |

## Decision Update Process

When a change impacts architecture-level behavior:

1. Document the proposed decision and alternatives.
2. Identify impacted layers and contracts.
3. Update or add ADR text where appropriate.
4. Add/adjust tests that prove the new invariant.
5. Update this report section and linked architecture pages.

## Key Files to Read Next

- `docs/adr/intent-first-contract.md`
- `packages/stackwarden/src/stackwarden/resolvers/resolver.py`
- `packages/stackwarden/src/stackwarden/domain/ensure.py`
- `packages/stackwarden/src/stackwarden/web/app.py`
- `apps/web/src/composables/useEntityCreateFlow.ts`
