# Repository Layout Guide

This document explains the Stacksmith file structure, why each directory exists, and where new files should go.

## Design Goals

- Keep source code, app surfaces, authored specs, operations, and docs clearly separated.
- Make ownership obvious so contributors can navigate quickly.
- Avoid top-level sprawl by giving each directory one primary responsibility.

## Top-Level Structure

## `apps/`

Runtime surfaces that users or operators run directly.

- `apps/api/`: API runtime surface wrappers and app-level API startup context.
- `apps/web/`: Vue frontend app (UI source, tests, and web build tooling).
- `apps/cli/` (optional): CLI surface docs/wrappers only (core CLI implementation remains in package code).

Why it exists:

- Keeps user-facing executables grouped in one place.
- Provides a clean boundary between "apps we run" and "libraries we maintain."

## `packages/`

Reusable implementation packages.
- `packages/stacksmith/src/stacksmith/`: canonical Python package source.

Why it exists:

- Keeps package code isolated from app wrappers and repo tooling.
- Supports standard Python packaging and testing workflows.

## `specs/`

Authored YAML contracts and compatibility catalogs.

- `specs/profiles/`
- `specs/stacks/`
- `specs/blocks/`
- `specs/rules/`
- `specs/templates/`

Why it exists:

- Keeps user-authored intent/configuration separate from executable code.
- Makes it explicit what data drives resolver/build behavior.

## `generated/`

Generated, derived, or compiled outputs (resolver artifacts, compiled specs, transient build metadata).

Why it exists:

- Prevents generated data from drifting into authored source trees.
- Keeps `specs/` focused on canonical, human-authored contracts.

## `ops/`

Operational scripts and deployment artifacts.

- `ops/scripts/`: local dev and service orchestration shell scripts.
- `ops/systemd/`: systemd unit files and deployment-facing service config.

Why it exists:

- Separates runtime operations from app/package source.
- Makes deployment and local service management easy to find.

## `docs/`

Project documentation and architecture references.

- high-level docs, ADRs, project reports, operational guidance, and examples docs.

Why it exists:

- Keeps documentation first-class and centralized.
- Supports onboarding and long-term maintainability.

## `tests/`

Backend, contract, and integration/regression tests.
Frontend tests live with the web app in `apps/web/tests/`.

Why it exists:

- Maintains a clear root test surface for Python/contract validation.
- Keeps test discovery predictable in CI and local workflows.

## `tools/`

Compatibility entrypoints and developer utilities.

Why it exists:

- Preserves stable command paths for existing workflows.
- Keeps legacy wrappers separate from canonical operational scripts in `ops/scripts/`.

## Directory Placement Rules

Use these rules when adding files:

- New Python module used by CLI/API/shared logic -> `packages/stacksmith/src/stacksmith/...`
- New UI component/view/composable -> `apps/web/src/...`
- New authored stack/profile/block/rule/template data -> `specs/...`
- New generated/compiled resolver output -> `generated/...`
- New run/deploy shell script -> `ops/scripts/...` (optionally add thin wrapper in `tools/` if needed)
- New service unit/deployment file -> `ops/systemd/...`
- New architecture or contributor docs -> `docs/...`
- New backend/unit/contract tests -> `tests/...`
- New frontend unit/component tests -> `apps/web/tests/...`

## What Should Not Go Where

- Do not put runtime/package source in `ops/`.
- Do not put authored specs in `packages/`.
- Do not add net-new operational scripts directly in `tools/` (use `ops/scripts/` and wrapper only if compatibility is required).
- Do not place generated artifacts under `specs/`, `packages/`, or `apps/` (use `generated/` or ignored local output paths).

## Ownership Summary

- `apps/`: experience/runtime surfaces
- `packages/`: core implementation
- `specs/`: authored input contracts and catalogs
- `generated/`: derived/generated outputs
- `ops/`: execution/deploy mechanics
- `tools/`: compatibility wrappers and developer utilities
- `docs/`: knowledge and architecture
- `tests/`: quality and regression guardrails
