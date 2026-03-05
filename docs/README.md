# Documentation Index

Complete map of all StackWarden documentation. See also the [root README](../README.md) for Quick Start and project overview.

## For Users

| Document | Description |
|----------|-------------|
| [reference.md](reference.md) | Full user reference -- profiles, stacks, blocks, drift detection, variants, registry policies, SBOM, fingerprinting, troubleshooting, and deprecations |
| [reference.md#build-performance-layered-overlay-strategy](reference.md#build-performance-layered-overlay-strategy) | Layered overlay build performance guidance for faster incremental rebuilds |
| [cli_wizard_usage.md](cli_wizard_usage.md) | CLI wizard commands and flags for creating profiles, blocks, and stacks interactively |
| [hardware_detection_matrix.md](hardware_detection_matrix.md) | How host hardware facts are detected, which fields are covered, and the catalog reconciliation process |
| [examples/example_plans.md](examples/example_plans.md) | Sample `stackwarden plan` outputs for common profile/stack combinations |
| [examples/](examples/) | Example workspaces (RL, robotics) used by stack file-copy directives |

## For Contributors

| Document | Description |
|----------|-------------|
| [project-report/README.md](project-report/README.md) | Index for the 10-chapter architecture deep-dive; start here for contributor reading paths |
| [project-report/01-philosophy-and-principles.md](project-report/01-philosophy-and-principles.md) | Design philosophy: intent-first contracts, determinism, and provenance |
| [project-report/02-system-architecture.md](project-report/02-system-architecture.md) | System architecture overview -- domain layers, data flow, and component boundaries |
| [project-report/03-cli-architecture.md](project-report/03-cli-architecture.md) | CLI layer design: Typer commands, shared decorators, and wizard flows |
| [project-report/04-web-api-architecture.md](project-report/04-web-api-architecture.md) | Web API layer: FastAPI routes, session auth boundaries, job streaming, and schema contracts |
| [project-report/05-web-ui-architecture.md](project-report/05-web-ui-architecture.md) | Web UI layer: Vue 3 SPA routes/guards, session-aware workflows, composables, and entity tables |
| [project-report/06-cross-layer-interactions.md](project-report/06-cross-layer-interactions.md) | How CLI, API, and UI layers interact through the shared domain |
| [project-report/07-design-decisions-and-adrs.md](project-report/07-design-decisions-and-adrs.md) | Key design decisions and architecture decision records |
| [project-report/08-onboarding-guide.md](project-report/08-onboarding-guide.md) | First-day setup using current Makefile workflow, mental model, repository walkthrough, and suggested first contributions |
| [project-report/09-testing-and-quality-strategy.md](project-report/09-testing-and-quality-strategy.md) | Testing strategy: unit, contract, integration, frontend, auth/session, and stress checks |
| [project-report/10-glossary-and-concepts.md](project-report/10-glossary-and-concepts.md) | Glossary of StackWarden-specific terms and concepts |
| [adr/intent-first-contract.md](adr/intent-first-contract.md) | ADR: intent-first contract design -- frozen terminology, ownership, and precedence |
| [repository_layout.md](repository_layout.md) | Monorepo directory structure, placement rules, and ownership summary |
| [cli_wizard_parity_matrix.md](cli_wizard_parity_matrix.md) | Parity matrix between web UI wizards and CLI wizards |
| [cli_release_review.md](cli_release_review.md) | CLI production-readiness checklist and release gates |

## For Operators

| Document | Description |
|----------|-------------|
| [reference.md#prerequisites](reference.md#prerequisites) | Required and optional software (Docker, Buildx, NVIDIA toolkit, SBOM tools) |
| [reference.md#drift-detection](reference.md#drift-detection) | How drift is detected and how `--immutable` works in CI |
| [reference.md#registry-policies](reference.md#registry-policies) | Configuring trusted registries (allow/deny lists) |
| [reference.md#deprecation-policy](reference.md#deprecation-policy) | Two-step deprecation process and current deprecations |

## Internal / Tracking

| Document | Description |
|----------|-------------|
| [devlog.md](devlog.md) | Development log with dated entries |
| [metrics/intent-first-metrics.md](metrics/intent-first-metrics.md) | Phase 0 metrics specification for intent-first adoption tracking |
