# Web UI Architecture

## Role of the Web UI

The Web UI provides guided authoring and operational workflows for profiles, stacks, blocks, planning, and artifact/job visibility. It is designed to make complex compatibility and build behavior understandable and actionable.

Primary frontend stack:

- Vue 3 + TypeScript
- Vue Router
- Vite build/dev tooling
- Vitest + Vue Test Utils

Core location: `apps/web/src`

## Frontend Structure

High-level organization:

- Views/pages: `apps/web/src/views`
- Reusable components: `apps/web/src/components`
- API client and endpoint wrappers: `apps/web/src/api`
- Stateful workflow composables: `apps/web/src/composables`
- Utility helpers: `apps/web/src/utils`

This structure keeps views orchestration-focused while moving reusable logic into composables/components.

## Routing and State Patterns

Routing is centralized in `apps/web/src/router.ts` with list/detail/edit and workflow routes for entity domains and operations.

State model:

- Local reactive state (`ref`, `computed`, `watch`) in pages/composables
- Shared workflow abstractions in composables (for example, entity list page and create flow helpers)
- No heavy global store as primary pattern for current architecture

## Data-Fetching and API Integration

Frontend API integration is centered on:

- `apps/web/src/api/client.ts` for fetch behavior, auth header, timeout, and error normalization
- `apps/web/src/api/endpoints.ts` for domain-specific API methods

Authentication model:

- Bearer token stored in local storage and attached to API and SSE requests

Long-running job observability:

- SSE job streaming in `apps/web/src/composables/useJobStream.ts`

## UX and Design Philosophy

Key UI patterns:

- Modal-first create and editing flows for authoring consistency
- Guided wizards for structured input and reduced user error
- Dry-run and confirm-write flow to preserve explicit mutation semantics
- Explainability surfaces for compatibility output, decision traces, and errors

Styling approach:

- Global design tokens and base styles in `apps/web/src/style.css`
- Component-scoped styles for local structure and maintainability

## Build and Deployment Linkage

Development and deployment coupling:

- Vite dev proxy forwards `/api` requests to backend server
- Production frontend build outputs static assets to backend static path (`packages/stackwarden/src/stackwarden/web/static`)
- Backend serves SPA assets and fallback routing through FastAPI app

This keeps deployment simple and tightly integrated with backend distribution.

## Testing Strategy for UI

Frontend tests are focused on API client behavior, stream handling, and key view flows.

Representative tests:

- `apps/web/tests/api-client.spec.ts`
- `apps/web/tests/job-stream.spec.ts`
- `apps/web/tests/blocks-view-modal.spec.ts`

CI includes frontend install/test/build to maintain UI/API contract health.

## Key Files to Read Next

- `apps/web/src/router.ts`
- `apps/web/src/api/client.ts`
- `apps/web/src/composables/useEntityCreateFlow.ts`
- `apps/web/src/composables/useJobStream.ts`
- `apps/web/src/views/CatalogView.vue`

## Common Modification Scenarios

- Add a new view workflow: create route + view + composable + endpoint integration + tests.
- Improve form UX: update wizard/create modal patterns while preserving dry-run/confirm steps.
- Extend streaming behavior: update job stream composable and matching UI state transitions.
