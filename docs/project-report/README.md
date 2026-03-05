# Stacksmith End-to-End Project Report

This documentation set explains Stacksmith from first principles through implementation details across the CLI, Web API, and Web UI. It is written for operators, integrators, and open-source contributors who need a fast but accurate understanding of how the system works and why it is designed this way.

## Read This First

- New contributors: start with [Philosophy and Principles](./01-philosophy-and-principles.md), then [System Architecture](./02-system-architecture.md), then [Onboarding Guide](./08-onboarding-guide.md).
- CLI-first users: read [CLI Architecture](./03-cli-architecture.md) and [Cross-Layer Interactions](./06-cross-layer-interactions.md).
- API integrators: read [Web API Architecture](./04-web-api-architecture.md), then [Testing and Quality Strategy](./09-testing-and-quality-strategy.md).
- Frontend contributors: read [Web UI Architecture](./05-web-ui-architecture.md), then [Design Decisions and ADRs](./07-design-decisions-and-adrs.md).

## Report Structure

1. [Philosophy and Principles](./01-philosophy-and-principles.md)
2. [System Architecture](./02-system-architecture.md)
3. [CLI Architecture](./03-cli-architecture.md)
4. [Web API Architecture](./04-web-api-architecture.md)
5. [Web UI Architecture](./05-web-ui-architecture.md)
6. [Cross-Layer Interactions](./06-cross-layer-interactions.md)
7. [Design Decisions and ADRs](./07-design-decisions-and-adrs.md)
8. [Onboarding Guide](./08-onboarding-guide.md)
9. [Testing and Quality Strategy](./09-testing-and-quality-strategy.md)
10. [Glossary and Concepts](./10-glossary-and-concepts.md)

## Scope and Grounding

This report is aligned with:

- Main project architecture in [README](../../README.md)
- Intent-first ADR in [docs/adr/intent-first-contract.md](../adr/intent-first-contract.md)
- CLI operational docs in [docs/cli_release_review.md](../cli_release_review.md) and [docs/cli_wizard_usage.md](../cli_wizard_usage.md)

If implementation and docs ever diverge, treat code-level behavior as source of truth and update this report accordingly.
