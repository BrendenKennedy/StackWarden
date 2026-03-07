# Remediation Roadmap

## PR Batch Sequence

### PR1 - Contract parity and schema canonicalization

- Findings: `AUD-001`, `AUD-002`
- Scope: contract policy docs + contract sync tests
- Owner: API + UI
- Outcome target: explicit canonical source and stronger drift detection

### PR2 - Blocks/Layers legacy cleanup

- Findings: `AUD-003`, `AUD-007`
- Scope: compatibility redirects, alias shims, migration notes
- Owner: Core + UI
- Outcome target: controlled deprecation path without user-facing regressions

### PR3 - Boundary enforcement and mapper normalization

- Findings: `AUD-005`, `AUD-006`
- Scope: architecture guards and DTO mapping boundaries
- Owner: Core
- Outcome target: stop new coupling and prepare staged decoupling

### PR4 - Style and naming consistency sweep

- Findings: `AUD-004` (naming migration prep), plus S2/S3 hygiene work
- Scope: naming standards, decomposition candidates, consistent adapter error handling
- Owner: Core + UI
- Outcome target: reduced cognitive overhead and consistent terminology

### PR5 - Quality-gate alignment and closure

- Scope: CI checks alignment, closure evidence, residual-risk acceptance list
- Owner: Engineering lead
- Outcome target: auditable sign-off package
