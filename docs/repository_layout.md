# Repository Layout Guide

This document explains the StackWarden file structure, why each directory exists, and where new files should go.

## Design Goals

- Keep source code, app surfaces, authored specs, operations, and docs clearly separated.
- Make ownership obvious so contributors can navigate quickly.
- Avoid top-level sprawl by giving each directory one primary responsibility.

## Top-Level Structure

## `apps/`

Runtime surfaces that users or operators run directly.

- `apps/web/`: Vue frontend app (UI source, tests, and web build tooling).

CLI and API entry points are defined in `pyproject.toml` `[project.scripts]` and live in the `packages/stackwarden` package.

Why it exists:

- Keeps user-facing app source grouped in one place.
- Provides a clean boundary between "apps we run" and "libraries we maintain."

## `packages/`

Reusable implementation packages.
- `packages/stackwarden/src/stackwarden/`: canonical Python package source.

Why it exists:

- Keeps package code isolated from app wrappers and repo tooling.
- Supports standard Python packaging and testing workflows.

## `services/`

Standalone ML API services (FastAPI stubs).

Each subdirectory is a self-contained service with a `main.py` entry point:
`agentic_rag_api`, `asr_api`, `diffusion_api`, `embedding_api`, `flux_schnell_api`, `llm_api`, `ollama_chat`, `rag_api`, `tts_api`, `vision_api`.

Why it exists:

- Groups ML inference and model-serving endpoints separate from the core StackWarden package.
- Each service can be deployed independently with its own container.

## `specs/`

Authored YAML contracts, compatibility catalogs, and runtime configs.

- `specs/profiles/`
- `specs/stacks/`
- `specs/blocks/`
- `specs/rules/`
- `specs/templates/`
- `specs/configs/`: runtime configuration files (finetune, NeMo, etc.)

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

Project documentation, architecture references, and example material.

- High-level docs, ADRs, project reports, and operational guidance.
- `docs/examples/`: example workspaces and reference scripts.

Why it exists:

- Keeps documentation first-class and centralized.
- Supports onboarding and long-term maintainability.

## `tests/`

Backend, contract, and integration/regression tests.
Frontend tests live with the web app in `apps/web/tests/`.

Why it exists:

- Maintains a clear root test surface for Python/contract validation.
- Keeps test discovery predictable in CI and local workflows.

## Directory Placement Rules

Use these rules when adding files:

- New Python module used by CLI/API/shared logic -> `packages/stackwarden/src/stackwarden/...`
- New UI component/view/composable -> `apps/web/src/...`
- New ML API service -> `services/<service_name>/`
- New authored stack/profile/block/rule/template/config data -> `specs/...`
- New generated/compiled resolver output -> `generated/...`
- New run/deploy shell script or developer utility -> `ops/scripts/...`
- New service unit/deployment file -> `ops/systemd/...`
- New architecture or contributor docs -> `docs/...`
- New example workspaces or reference material -> `docs/examples/`
- New backend/unit/contract tests -> `tests/...`
- New frontend unit/component tests -> `apps/web/tests/...`

## What Should Not Go Where

- Do not put runtime/package source in `ops/`.
- Do not put authored specs in `packages/`.
- Do not place generated artifacts under `specs/`, `packages/`, or `apps/` (use `generated/` or ignored local output paths).

## Ownership Summary

- `apps/`: experience/runtime surfaces (Vue frontend)
- `packages/`: core implementation
- `services/`: ML API services (FastAPI stubs)
- `specs/`: authored input contracts, catalogs, and configs
- `generated/`: derived/generated outputs
- `ops/`: execution/deploy mechanics and developer utilities
- `docs/`: knowledge, architecture, and examples
- `tests/`: quality and regression guardrails
