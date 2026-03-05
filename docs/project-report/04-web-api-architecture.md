# Web API Architecture

## Role of the Web API

The Web API is the contract-driven integration surface for web clients and external automation that prefer HTTP over direct CLI invocation. It exposes create/plan/ensure/catalog/system workflows while reusing shared core business logic.

Primary app modules:

- App factory and middleware: `packages/stacksmith/src/stacksmith/web/app.py`
- Entrypoint: `packages/stacksmith/src/stacksmith/web_entry.py`
- Environment settings: `packages/stacksmith/src/stacksmith/web/settings.py`
- Route modules: `packages/stacksmith/src/stacksmith/web/routes/*`

## App Lifecycle and Middleware

`create_app()` configures middleware, error handlers, route wiring, and static SPA fallback. Lifespan startup initializes shared dependencies (catalog, job manager) through `packages/stacksmith/src/stacksmith/web/deps.py`.

Core middleware responsibilities:

- CORS in development mode where configured
- Bearer token auth protection for `/api/*` (except health endpoint)
- Unified exception normalization for domain and validation errors

## Route Domains

Route modules are organized by domain intent:

- Entities: `profiles.py`, `stacks.py`, `blocks.py`
- Creation and composition: `create.py`, `plan.py`, `compatibility.py`, `verify.py`
- Job orchestration and streaming: `jobs.py`
- Persistence and artifacts: `catalog.py`, `artifacts.py`
- System and metadata: `system.py`, `settings.py`, `detection.py`, `meta.py`

This grouping mirrors operator tasks rather than low-level subsystem internals.

## Contracts and Versioning

Request/response DTOs are centralized in `packages/stacksmith/src/stacksmith/web/schemas.py`. API contract/version behavior is supported by `packages/stacksmith/src/stacksmith/web/util/versioning.py`.

Design intent:

- Maintain explicit transport contracts even when internals evolve.
- Normalize validation payloads into stable shapes for UI and integrations.
- Keep domain errors mapped consistently to HTTP semantics.

## Security Model

Security is token-based perimeter control with separate scopes:

- Primary bearer token for API access
- Admin token header for privileged settings/catalog mutations

Security hardening patterns include:

- constant-time token comparison
- path traversal protections on file/path sensitive routes
- structured input allowlists and field validation for create/update endpoints

## Long-Running Work: Jobs and SSE

`POST /api/ensure` performs validation and planning admission checks, persists a job, and schedules background execution.

Job lifecycle support:

- Job store: `packages/stacksmith/src/stacksmith/web/jobs/store.py`
- Manager/runners: `packages/stacksmith/src/stacksmith/web/jobs/manager.py`, `packages/stacksmith/src/stacksmith/web/jobs/runners.py`
- Event streaming via SSE endpoints for live logs and status transitions

This design enables responsive UI workflows while preserving backend execution authority.

## API-to-Core Integration

The API reuses shared core behavior rather than implementing parallel business logic. Critical shared paths include:

- `packages/stacksmith/src/stacksmith/domain/ensure.py`
- `packages/stacksmith/src/stacksmith/application/create_flows.py`
- `packages/stacksmith/src/stacksmith/resolvers/resolver.py`

This keeps CLI and API semantics aligned for planning and execution.

## Testing Strategy for API

API tests use FastAPI `TestClient` and integration-oriented coverage with selective patching for expensive runtime operations.

Representative suites:

- `tests/web/test_create.py`
- `tests/web/test_jobs_plan_verify_artifacts.py`
- `tests/web/test_entity_api.py`
- `tests/web/test_settings_catalog.py`
- `tests/web/test_compatibility_api.py`

Focus areas include response contracts, status codes, lifecycle transitions, and resilience behavior.

## Key Files to Read Next

- `packages/stacksmith/src/stacksmith/web/app.py`
- `packages/stacksmith/src/stacksmith/web/routes/jobs.py`
- `packages/stacksmith/src/stacksmith/web/schemas.py`
- `packages/stacksmith/src/stacksmith/web/util/validation.py`
- `tests/web/test_jobs_plan_verify_artifacts.py`

## Common Modification Scenarios

- Add endpoint: define DTOs, route handler, shared-core call, and contract tests.
- Extend auth behavior: update middleware/settings plus route-specific privilege checks.
- Add async workflow stage: evolve job manager/store/event contract in lockstep with UI consumers.
