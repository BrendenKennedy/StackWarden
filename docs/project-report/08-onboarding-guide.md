# Onboarding Guide

## Audience and Goal

This guide helps new open-source contributors understand Stacksmith quickly and make safe, meaningful changes within their first day.

## First-Day Setup

## 1) Local Environment

Prerequisites:

- Python 3.10+
- Docker with buildx
- Optional NVIDIA runtime for GPU profile workflows

Bootstrap:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Sanity checks:

```bash
stacksmith doctor
python -m pytest tests/ -v
```

## 2) Mental Model First

Before editing code, understand this flow:

1. User intent is authored in stacks/blocks.
2. Profile captures host facts and constraints.
3. Resolver derives deterministic compatible plan.
4. Ensure executes build/pull and writes catalog lifecycle state.

Read in this order:

1. `README.md`
2. `docs/adr/intent-first-contract.md`
3. `docs/project-report/02-system-architecture.md`
4. `docs/project-report/06-cross-layer-interactions.md`

## 3) Repository Walkthrough

Core backend:

- `packages/stacksmith/src/stacksmith/domain`: canonical models and invariants
- `packages/stacksmith/src/stacksmith/resolvers`: compatibility/rules and plan logic
- `packages/stacksmith/src/stacksmith/builders`, `packages/stacksmith/src/stacksmith/runtime`: execution side effects
- `packages/stacksmith/src/stacksmith/catalog`: persistent artifact lifecycle store

Surfaces:

- CLI: `packages/stacksmith/src/stacksmith/cli.py`
- Web API: `packages/stacksmith/src/stacksmith/web/*`
- Web UI: `apps/web/src/*`

Specs and data:

- `specs/profiles/`, `specs/stacks/`, `specs/blocks/`, `specs/rules/`, `specs/templates/`
- `ops/scripts/` for operational shell workflows
- `ops/systemd/` for service unit deployment artifacts

## 4) Where to Change What

- Add or adjust business logic: start in domain/application/resolver modules.
- Add CLI behavior: wire command in `packages/stacksmith/src/stacksmith/cli.py` using shared core calls.
- Add API behavior: add route and schemas in `packages/stacksmith/src/stacksmith/web/routes` and `packages/stacksmith/src/stacksmith/web/schemas.py`.
- Add UI workflow: update `apps/web/src/views`, `components`, `composables`, and endpoint wrappers.

Avoid:

- Duplicating core logic in CLI handlers or API routes.
- Embedding domain decisions in frontend-only code.

## 5) Suggested First Contributions

- Improve docs consistency and examples.
- Add tests for existing edge cases in compatibility or create flows.
- Tighten validation messages and UI error clarity.
- Add small UX polish while preserving dry-run/confirm semantics.

## 6) Development and Verification Workflow

Recommended loop:

1. Make smallest safe change in correct layer.
2. Run targeted tests for touched area.
3. Run broader tests if contracts changed.
4. Update docs when user-facing semantics shift.

Minimum checks:

- Backend tests touching changed modules
- Frontend tests for changed UI/API behavior
- Architecture and contract tests when cross-layer behavior changes

## 7) Contribution Style and Expectations

- Keep changes purpose-driven and scoped.
- Preserve determinism and compatibility explainability.
- Maintain contract stability unless intentionally versioning a change.
- Include tests with new behavior.
- Keep docs aligned with implementation.

## 8) Getting Unstuck

When blocked:

- Trace from surface to core and identify boundary mismatch.
- Check existing tests for expected behavior and conventions.
- Inspect compatibility/resolver outputs before runtime debugging.
- Open a draft issue/PR summarizing intent, observed behavior, and proposed boundary-safe fix.

## Quick Reference Links

- Architecture: `docs/project-report/02-system-architecture.md`
- CLI details: `docs/project-report/03-cli-architecture.md`
- API details: `docs/project-report/04-web-api-architecture.md`
- UI details: `docs/project-report/05-web-ui-architecture.md`
- Test strategy: `docs/project-report/09-testing-and-quality-strategy.md`
