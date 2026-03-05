# Intent-First Metrics Specification (Phase 0)

## Objective
Define success metrics and event taxonomy for declarative derivation adoption before schema and resolver changes land.

## Primary Metrics

### 1) Time to first working container
- **Definition:** Time from first create attempt (stack/profile path) to first successful container plan/build outcome.
- **Formula:** `first_success_timestamp - first_attempt_timestamp`
- **Dimensions:** `schema_version`, `host_class`, `runtime_family`, `stack_kind`.

### 2) Auto-resolved build rate
- **Definition:** Percent of successful outcomes that complete without manual override.
- **Formula:** `successful_without_override / total_successful`
- **Dimensions:** `schema_version`, `profile_kind`, `stack_kind`, `runtime_family`.

### 3) Override rate
- **Definition:** Share of flows that required explicit advanced/manual override.
- **Formula:** `override_applied_count / total_create_or_ensure_flows`
- **Dimensions:** `schema_version`, `host_class`, `intent_needs_count`.

### 4) Failure reason distribution
- **Definition:** Breakdown of non-success outcomes by standardized reason.
- **Categories:** `host_mismatch`, `dependency_conflict`, `policy_restriction`, `unknown`.
- **Formula:** `count_by_reason / total_failures`

## Event Taxonomy
- `create_attempt`
- `create_result`
- `dry_run_attempt`
- `dry_run_result`
- `compose_attempt`
- `compose_result`
- `build_result`
- `override_applied`
- `fallback_applied`

## Required Event Fields
- `event_name`
- `entity_type` (`profile`, `stack`, `block`)
- `entity_id`
- `schema_version`
- `outcome` (`success`, `validation_error`, `conflict`, `failure`)
- `duration_ms`
- `failure_reason` (nullable; one of taxonomy values)
- `has_override`
- `host_class` (`gpu`, `cpu`, `unknown`)
- `runtime_family` (for example `nvidia`, `docker`, `unknown`)

## Initial Instrumentation Targets
- Backend create/dry-run/compose routes in `stackwarden/web/routes/create.py`.
- Optional client funnel enrichment in `apps/web/src/api/client.ts` and create views.

## Baseline Procedure
1. Capture baseline for legacy flow prior to Phase 1 rollout.
2. Store baseline with schema version and date window.
3. Recompute after Phase 1 to detect regressions and directional improvement.

## Reporting Cadence
- Daily for rollout week.
- Weekly thereafter until Phase 2 derivation engine rollout.

## Ownership
- Product owner: metric definitions and target thresholds.
- Platform owner: server-side instrumentation and quality gates.
- Frontend owner: optional funnel annotations and UI-level conversion context.
