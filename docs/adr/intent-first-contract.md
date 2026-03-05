# ADR: Blocks-First Declarative Derivation Contract

## Status
Accepted (Phase 0 baseline)

## Context
Stacksmith currently accepts a mix of user-authored capability data and detected host facts, then resolves compatible stacks and builds. As features grow, implementation details are leaking into user input, making onboarding and explainability harder.

This ADR defines the blocks-first contract:
- User intent is declared by selecting `stack.blocks`.
- Profiles describe host facts and policy restrictions.
- System derives implementation outputs deterministically.

## Contract Statement
Users declare desired functionality by choosing **blocks**; Stacksmith derives compatible implementation details from block requirements, host facts, and restrictions, and records a **decision_trace** for every derived output.

## Frozen Terminology
- `blocks`: primary user intent contract.
- `intent`: optional metadata, not the primary user contract.
- `requirements`: optional metadata, not the primary user contract.
- `derived_capabilities`: system-computed capabilities used for compatibility and planning.
- `host_facts`: detected or inferred host/runtime observations with confidence.
- `decision_trace`: ordered rationale statements describing why values were derived or selected.

## Ownership Model
- **User-authored input:** `stack.blocks`, explicit profile restrictions, optional metadata/legacy fields.
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
- User selects blocks that require GPU acceleration.
- System derives `derived_capabilities` including `cuda`.
- `decision_trace` captures host/runtime evidence and any fallback decisions.

### Example B: CPU-only host
- Host facts indicate no GPU runtime.
- User selects generic service blocks.
- System derives CPU-safe capability set with no CUDA dependency.
- `decision_trace` records GPU absence and selected non-GPU path.

### Example C: Partial/uncertain detection
- Host facts include unknown runtime version confidence.
- User selects blocks and strict profile restrictions.
- System derives conservative defaults and emits fix suggestions.
- `decision_trace` includes uncertainty and reason for conservative selection.

## Consequences
- UX can simplify around block selection while preserving an advanced override path.
- Resolver and compatibility checks can converge on derived outputs instead of ad hoc/manual capability gating.
- Explainability becomes a first-class API contract rather than an optional debug artifact.
