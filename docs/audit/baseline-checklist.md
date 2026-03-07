# Baseline Checklist

## Scope

- In scope: `apps/web`, `packages/stackwarden`, `specs`
- Out of scope for this pass: broad docs rewrite, non-product directories except quality-gate references

## Baseline Sources

- ADR contract baseline: `docs/adr/intent-first-contract.md`
- System boundaries: `docs/project-report/02-system-architecture.md`
- API architecture and route responsibilities: `docs/project-report/04-web-api-architecture.md`
- UI structure and data-fetching patterns: `docs/project-report/05-web-ui-architecture.md`
- Repository placement rules: `docs/repository_layout.md`
- Existing quality gates: `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml`, `tests/test_contract_sync.py`, `tests/test_architecture_guards.py`

## Accepted Audit Control Families

- Contract and schema parity
- Legacy/orphaned path control
- Architectural boundary conformance
- Naming and terminology consistency
- Style/tooling consistency
- Verification and regression evidence

## Pass/Fail Rules For This Audit

1. No unresolved S0/S1 findings in scoped product code at close.
2. Canonical contract source is explicit and frontend/backend drift checks are documented.
3. Blocks-to-Layers legacy aliases are either removed or tracked with explicit deprecation rationale.
4. Boundary violations have documented owners and remediation sequencing.
5. Quality-gate evidence is captured (tests/checks run and outcomes logged).

## Severity Rubric

- S0 Critical: correctness/security/data corruption/contract break
- S1 High: architecture drift or major schema/model inconsistency with broad confusion risk
- S2 Medium: anti-patterns, partial standardization, moderate duplication
- S3 Low: style/naming hygiene issues without material behavior risk

## Priority Model

Priority = `Severity x BlastRadius x Confidence - RemediationCostModifier`

- BlastRadius: number of modules/flows touched
- Confidence: evidence quality (tests/repro/explicit references)
- RemediationCostModifier: complexity/risk of immediate fix
