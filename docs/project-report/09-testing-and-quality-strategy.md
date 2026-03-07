# Testing and Quality Strategy

## Quality Goals

StackWarden quality strategy focuses on deterministic behavior, contract stability, and safe lifecycle transitions across CLI, API, and UI surfaces.

## Test Strategy by Layer

## Core Domain and Resolver

Objectives:

- preserve deterministic planning behavior
- validate compatibility decisions and invariants
- protect fingerprinting and lifecycle semantics

Representative areas:

- resolver compatibility/rule logic
- ensure lifecycle transitions
- schema and contract synchronization tests

## CLI Layer

Objectives:

- command behavior parity with shared core
- robust argument/error handling
- stable machine-readable output where applicable

Typical approach:

- Typer `CliRunner`
- environment and dependency patching for controlled scenarios

Representative suites:

- `tests/test_cli_build_and_wizard.py`
- `tests/test_cli_operations.py`
- `tests/test_cli_catalog.py`
- `tests/test_cli_parity.py`

## Web API Layer

Objectives:

- HTTP contract correctness (status, shape, validation)
- session auth enforcement and setup/login/change-password behavior
- async job and streaming lifecycle integrity

Typical approach:

- FastAPI `TestClient`
- dependency overrides and targeted mocking for runtime-heavy paths

Representative suites:

- `tests/web/test_create.py`
- `tests/web/test_jobs_plan_verify_artifacts.py`
- `tests/web/test_entity_api.py`
- `tests/web/test_settings_catalog.py`
- `tests/web/test_auth_session.py`
- `tests/web/test_jobs_stress_edge_cases.py`

## Web UI Layer

Objectives:

- resilient API client behavior and error normalization
- reliable job streaming state transitions
- stable view/component workflows for authoring and operations

Typical approach:

- Vitest + Vue Test Utils

Representative suites:

- `apps/web/tests/api-client.spec.ts`
- `apps/web/tests/job-stream.spec.ts`
- `apps/web/tests/blocks-view-modal.spec.ts`
- `apps/web/tests/route-deprecations.spec.ts`

## Architecture and Contract Guards

Critical guardrails:

- architecture boundary tests to prevent improper coupling
- contract synchronization tests where frontend/backend API shapes must remain aligned
- regression checks around compatibility and deterministic outputs
- packaged static asset hygiene checks to prevent stale web bundles in backend static assets

These tests are high-value because they protect multi-layer coherence.

## CI Expectations

CI should validate:

- backend test suite
- frontend test suite
- frontend build
- lint/type checks where configured
- CLI+web API stress coverage (`make test-stress-e2e`) for regression discovery on repeated runs

When changing cross-layer behavior, include targeted tests in each impacted layer rather than relying on one surface only.

## Change-Type Verification Matrix

| Change Type | Must Verify |
| --- | --- |
| Resolver/rules update | compatibility tests, deterministic outputs, affected CLI/API tests |
| Ensure/build pipeline change | lifecycle tests, catalog state assertions, runtime path tests |
| API DTO/route change | web API contract tests, frontend endpoint/composable tests |
| UI create/flow change | frontend workflow tests, no contract regressions, manual smoke path |
| Catalog schema/store change | migration/store tests, API/CLI read-path checks |

## Manual Verification Checklist

Use this when automated coverage is incomplete for a change:

1. Run `plan` and verify deterministic response shape for known profile/stack.
2. Run `ensure` or API ensure flow and confirm status transitions.
3. Validate catalog view/search and artifact metadata visibility.
4. Confirm UI create flow dry-run and confirm-write behavior.
5. Verify compatibility messages remain explainable and actionable.

## Quality Risks to Watch

- Surface drift where CLI and API behavior diverge.
- Hidden side effects introduced into pure resolver code.
- Contract shape changes without frontend adaptation.
- Lifecycle transition changes without migration and state handling updates.

## Key Files to Read Next

- `tests/test_architecture_guards.py`
- `tests/test_cli_parity.py`
- `tests/web/test_jobs_plan_verify_artifacts.py`
- `apps/web/tests/api-client.spec.ts`
- `.github/workflows/ci.yml`
