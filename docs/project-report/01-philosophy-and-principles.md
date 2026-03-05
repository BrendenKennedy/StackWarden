# Philosophy and Principles

## Purpose

Stacksmith is a deterministic system for planning and producing ML container artifacts. It is built to make compatibility, reproducibility, and operational safety explicit instead of implicit.

At a product level:

- Users express intent using stack blocks.
- Profiles describe host facts and constraints.
- Resolver logic derives compatible implementation choices.
- Builders execute those choices and catalog records provenance and lifecycle.

## Core Philosophy

## 1) Intent-First Contract

The authored `stack.blocks` sequence is the primary intent surface. This separates *what the user wants* from *how the system realizes it* on specific hardware/runtime conditions.

Practical implications:

- Author intent in stacks and blocks, not by hardcoding ad hoc runtime behavior in profiles.
- Keep profile definitions focused on host facts, restrictions, and policy boundaries.
- Preserve block order semantics because composition precedence is meaningful.

## 2) Determinism by Default

Given equivalent inputs, Stacksmith aims to produce equivalent plans, fingerprints, and image tags.

Key deterministic inputs include:

- Profile and stack identity and content
- Selected base image and digest
- Composed dependency and runtime metadata
- Template/version metadata
- Variant overrides

Determinism reduces ambiguity in CI, drift analysis, and forensic troubleshooting.

## 3) Explainability Over Hidden Magic

Compatibility and plan outputs include warnings, errors, and decision traces so operators and contributors can understand system reasoning. This design favors visibility over opaque automation.

## 4) Explicit Side-Effect Boundaries

Resolver behavior is intentionally pure. Side effects (Docker/buildx/network/fs/catalog writes) are constrained to runtime, builder, and persistence layers.

This improves:

- testability of planning logic
- reliability of debugging and regression isolation
- confidence in using multiple orchestration surfaces (CLI and API) over shared core logic

## 5) Operational Safety and Governance

Stacksmith emphasizes controlled mutation of artifacts and clear lifecycle state transitions (`planned`, `building`, `built`, `failed`, `stale`).

Safety posture includes:

- preflight compatibility checks
- explicit rebuild/immutability semantics
- artifact drift detection
- registry policy and provenance labeling

## Design Principles by Layer

- CLI: scripted/operator ergonomics, clear risk framing, strict exit behavior.
- Web API: stable contracts, normalized validation and errors, token-gated mutation.
- Web UI: guided flows, dry-run/confirm patterns, decision visibility.
- Core domain: deterministic contracts and portable business logic shared by all surfaces.

## Trade-Offs Accepted

- More structure and metadata in exchange for clearer reasoning and safer operations.
- Additional upfront modeling effort to reduce downstream ambiguity.
- Strong compatibility checks that can block ambiguous builds early rather than failing late.

## Non-Goals

- Stacksmith is not a scheduler or workload orchestrator.
- Stacksmith is not a generic SAT solver for every dependency scenario.
- License policy tooling is advisory and does not replace legal review.

## Key Files to Read Next

- `README.md`
- `docs/adr/intent-first-contract.md`
- `packages/stacksmith/src/stacksmith/resolvers/resolver.py`
- `packages/stacksmith/src/stacksmith/domain/ensure.py`

## Common Modification Scenarios

- Extending intent model: update block schemas and composition logic first, then resolver rules.
- Tightening compatibility policy: adjust rule catalog and compatibility checks with contract tests.
- Changing reproducibility behavior: update fingerprint inputs and ensure drift logic remains coherent.
