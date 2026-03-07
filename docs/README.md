# Documentation Index

Start here for the minimum docs needed to use, operate, and contribute to StackWarden.

## Critical Path

- [Quick Start + Value Overview](../README.md)
- [Prerequisites](reference.md#prerequisites)
- [Full User Reference](reference.md)
- [CLI Wizard Usage](cli_wizard_usage.md)
- [Example Plans](examples/example_plans.md)

StackWarden is DGX Spark-first for bundled stacks, with best-effort support for non-DGX environments and explicit compatibility warnings.

## User Docs

| Document | Description |
|----------|-------------|
| [reference.md](reference.md) | Complete command and workflow reference |
| [reference.md#build-performance-layered-overlay-strategy](reference.md#build-performance-layered-overlay-strategy) | Incremental build performance guidance |
| [cli_wizard_usage.md](cli_wizard_usage.md) | Interactive profile/layer/stack creation |
| [hardware_detection_matrix.md](hardware_detection_matrix.md) | Hardware detection and reconciliation behavior |
| [examples/example_plans.md](examples/example_plans.md) | Common `stackwarden plan` outputs |
| [examples/](examples/) | Example workspaces (RL, robotics) used by stack file-copy directives |

## Contributor Docs

| Document | Description |
|----------|-------------|
| [project-report/README.md](project-report/README.md) | Full architecture deep-dive index |
| [project-report/01-philosophy-and-principles.md](project-report/01-philosophy-and-principles.md) | Core design principles |
| [project-report/02-system-architecture.md](project-report/02-system-architecture.md) | System layers and data flow |
| [project-report/03-cli-architecture.md](project-report/03-cli-architecture.md) | CLI architecture |
| [project-report/04-web-api-architecture.md](project-report/04-web-api-architecture.md) | API architecture and auth boundaries |
| [project-report/05-web-ui-architecture.md](project-report/05-web-ui-architecture.md) | Web UI architecture |
| [project-report/06-cross-layer-interactions.md](project-report/06-cross-layer-interactions.md) | Cross-layer interactions |
| [project-report/07-design-decisions-and-adrs.md](project-report/07-design-decisions-and-adrs.md) | Key design decisions and architecture decision records |
| [project-report/08-onboarding-guide.md](project-report/08-onboarding-guide.md) | Contributor onboarding |
| [project-report/09-testing-and-quality-strategy.md](project-report/09-testing-and-quality-strategy.md) | Testing strategy |
| [project-report/10-glossary-and-concepts.md](project-report/10-glossary-and-concepts.md) | Terminology and concepts |
| [adr/intent-first-contract.md](adr/intent-first-contract.md) | Intent-first contract ADR |
| [repository_layout.md](repository_layout.md) | Repository structure and placement rules |
| [cli_wizard_parity_matrix.md](cli_wizard_parity_matrix.md) | Parity matrix between web UI wizards and CLI wizards |
| [cli_release_review.md](cli_release_review.md) | CLI production-readiness checklist and release gates |

## Operator Docs

| Document | Description |
|----------|-------------|
| [reference.md#prerequisites](reference.md#prerequisites) | Runtime/software requirements |
| [reference.md#drift-detection](reference.md#drift-detection) | Drift detection and `--immutable` in CI |
| [reference.md#registry-policies](reference.md#registry-policies) | Trusted registry policy configuration |
| [reference.md#deprecation-policy](reference.md#deprecation-policy) | Deprecation lifecycle and active deprecations |

## Internal / Tracking

| Document | Description |
|----------|-------------|
| [devlog.md](devlog.md) | Development log with dated entries |
| [metrics/intent-first-metrics.md](metrics/intent-first-metrics.md) | Phase 0 metrics specification for intent-first adoption tracking |
