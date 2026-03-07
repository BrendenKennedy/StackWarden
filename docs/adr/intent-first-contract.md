# ADR: Layers-First Declarative Derivation Contract

## Status
Accepted (Phase 0 baseline)

## Context
StackWarden accepts user-authored intent plus detected host facts, then resolves compatible stacks and builds. This ADR keeps that contract explicit so onboarding and explainability remain strong as features evolve.

This ADR defines the layers-first contract:
- User intent is declared by selecting `stack.layers`.
- Profiles describe host facts and policy restrictions.
- System derives implementation outputs deterministically.

## Contract Statement
Users declare desired functionality by choosing **layers**; StackWarden derives compatible implementation details from layer requirements, host facts, and restrictions, and records a **decision_trace** for every derived output.

## Frozen Terminology
- `layers`: primary user intent contract.
- `intent`: optional metadata, not the primary user contract.
- `requirements`: optional metadata, not the primary user contract.
- `derived_capabilities`: system-computed capabilities used for compatibility and planning.
- `host_facts`: detected or inferred host/runtime observations with confidence.
- `decision_trace`: ordered rationale statements describing why values were derived or selected.

## Ownership Model
- **User-authored input:** `stack.layers`, explicit profile restrictions, optional metadata/legacy fields.
- **System-derived output:** `derived_capabilities`, selected/rejected feature candidates, fix suggestions, and `decision_trace`.
- **Observed facts:** `host_facts` (detected/inferred/unknown confidence attached per field).

## Precedence Policy
When deriving outputs, precedence is:
1. Explicit user constraints
2. Derived defaults
3. Heuristics

If two sources conflict, the higher-precedence source wins and the conflict is recorded in `decision_trace`.

## Compatibility Rules
- Existing payloads remain valid.
- Existing `profile.capabilities` is accepted as a legacy/manual input channel.
- `derived_capabilities` is canonical for computed capability state.
- Profile capability editing is not the primary UX path.
- User-supplied derived fields are normalized to system-computed values, with normalization rationale appended to `decision_trace`.

## Canonical Examples

### Example A: GPU host with strong detection
- Host reports NVIDIA runtime and CUDA-compatible driver.
- User selects layers that require GPU acceleration.
- System derives `derived_capabilities` including `cuda`.
- `decision_trace` captures host/runtime evidence and any fallback decisions.

### Example B: CPU-only host
- Host facts indicate no GPU runtime.
- User selects generic service layers.
- System derives CPU-safe capability set with no CUDA dependency.
- `decision_trace` records GPU absence and selected non-GPU path.

### Example C: Partial/uncertain detection
- Host facts include unknown runtime version confidence.
- User selects layers and strict profile restrictions.
- System derives conservative defaults and emits fix suggestions.
- `decision_trace` includes uncertainty and reason for conservative selection.

## Consequences
- UX can simplify around layer selection while preserving an advanced override path.
- Resolver and compatibility checks can converge on derived outputs instead of ad hoc/manual capability gating.
- Explainability becomes a first-class API contract rather than an optional debug artifact.

## Scope Boundary: Curated DGX First
- **Primary production path:** curated DGX profiles, tuples, and layer compatibility rules are the authoritative defaults for NVIDIA DGX deployments.
- **Secondary portability path:** auto-optimization remains available for heterogeneous or unknown hardware as best-effort guidance.
- **Resolver charter:** resolver outputs must remain deterministic and explainable, and every heuristic decision must be represented in `decision_trace` and plan metadata.

## Explicit Limitation Statement
- Auto-optimization is heuristic and intentionally bounded. It is not a global tuner and does not guarantee optimal performance for every hardware/workload combination.
- For production-grade reproducibility, curated profile/rule defaults override heuristic suggestions when conflicts exist.

## DGX-First Catalog Policy
- Bundled stacks use a mixed catalog model:
  - `dgx_compatible`: validated to run correctly on DGX-targeted paths.
  - `dgx_optimized`: tuned for DGX behavior but not yet fully certified.
  - `dgx_certified`: curated and benchmarked DGX-first path.
  - `generic_best_effort`: portable path that is allowed but not guaranteed to be performance-optimal outside curated DGX targets.
- Default behavior for non-DGX profiles remains **warn + allow** for DGX-certified stacks. Compatibility should emit an explicit warning and decision trace entry instead of hard-blocking by default.
