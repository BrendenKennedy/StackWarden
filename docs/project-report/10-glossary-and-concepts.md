# Glossary and Concepts

## Purpose

This glossary defines core StackWarden terminology used across CLI, API, UI, tests, and architecture docs.

## Core Concepts

## Profile

A host/runtime descriptor that captures machine facts and policy restrictions relevant to compatibility and build planning.

Profiles should describe environment reality and constraints, not user software intent.

## Stack

A workload intent specification describing what should be built/run, including ordered layer composition, runtime hints, and optional variants.

## Layer

A reusable intent unit used in recipe stacks. Layers compose into a concrete stack shape through deterministic merge and precedence rules.

## Stack Recipe

A stack form that references layers (`stack.layers`) as the primary intent surface. Composition resolves layer contributions into effective configuration.

## Resolver

The deterministic planning engine that evaluates profile + stack compatibility and computes an executable plan with decision trace data.

Resolver logic is intended to be side-effect free.

## Compatibility Preview

A preflight evaluation surface that reports whether a stack/profile combination is valid, with structured warnings, errors, and rationale.

## Ensure

The execution pipeline that takes validated plan inputs and performs build/pull actions, lifecycle updates, and provenance capture.

## Artifact

A built or referenced container output tracked by StackWarden with metadata, provenance, and lifecycle state.

## Catalog

The persistence layer (SQLite-backed) that stores artifact records, statuses, search metadata, and related lifecycle information.

## Artifact Lifecycle States

- `planned`: artifact record admitted before full execution
- `building`: active execution in progress
- `built`: successful output and metadata captured
- `failed`: execution or validation path failed
- `stale`: previously built artifact invalidated by drift

## Drift

A mismatch between current expected plan/provenance conditions and previously built artifact identity or metadata, which can trigger rebuild or immutable failure behavior.

## Fingerprint

A deterministic hash derived from plan-relevant inputs. It anchors artifact identity and supports reproducibility guarantees.

## Manifest

Captured metadata snapshot of resolved/installed package state and runtime details produced post-build for inspection and reproducibility workflows.

## Repro

A workflow to reconstruct a build from captured manifest/provenance data in a controlled, traceable manner.

## Variant

A controlled parameterized axis in stack definitions (for example, bool or enum choices) used to expand build matrix behavior deterministically.

## Tuple Layer

An architecture-aware decision layer that maps host/runtime facts to supported implementation paths with configurable enforcement modes.

## Create Flow

The layered process for authoring new profiles/stacks/layers, usually including validation, dry-run preview, and explicit confirm-write behavior.

## Job (Web)

An asynchronous API execution record for long-running operations (such as ensure) with persisted status and streamable logs/events.

## SSE (Server-Sent Events)

A unidirectional streaming mechanism used by the UI to receive live job updates from the API.

## Risk Tier (CLI)

Metadata grouping of commands by operational impact (`low_risk` and `high_risk`) used for release review and user/operator framing.

## Determinism

A system property where equivalent inputs produce equivalent planning/execution identity outcomes, reducing ambiguity in automation and diagnostics.

## Intent-First Contract

The principle that user intent should be expressed through stack/layer composition, with system behavior derived through compatibility and resolver logic.
