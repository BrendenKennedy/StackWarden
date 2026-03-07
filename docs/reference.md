# StackWarden Reference Guide

Operator-focused reference for CLI, API-facing behavior, and runtime workflows. For deeper architecture context, see the [project report](project-report/README.md).

## Prerequisites

Run `stackwarden doctor` first. Required and optional tools:

| Software | Purpose | Install |
|----------|---------|--------|
| **Docker** | Container runtime/build execution | [docker.com](https://docs.docker.com/get-docker/) |
| **Docker Buildx** | Overlay/multi-stage builds | Usually bundled with Docker |
| **NVIDIA Container Toolkit** (optional) | GPU runtime access | [NVIDIA docs](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) |
| **Docker Desktop** or **Syft** (optional) | SBOM generation | [Docker Desktop](https://www.docker.com/products/docker-desktop/) / [Syft](https://github.com/anchore/syft) |

## Fast Operator Loop

```bash
stackwarden doctor
stackwarden plan --profile dgx_spark --stack diffusion_fastapi
stackwarden ensure --profile dgx_spark --stack diffusion_fastapi
```

Use `--immutable` in CI to fail on drift instead of rebuilding.

## Profiles

Profiles describe host/runtime facts and constraints. They do not describe app intent.

### Guided setup (UI/API)

- UI flow: **Create Profile -> Guided Setup**
- API: `GET /api/system/detection-hints`, `GET /api/meta/create-contracts`
- Detection runs on the StackWarden server host (not the browser host).

### Profile example (`specs/profiles/*.yaml`)

```yaml
schema_version: 2
id: my_workstation
display_name: "My Workstation"
arch: amd64
os: linux
container_runtime: nvidia
cuda:
  major: 12
  minor: 4
  variant: cuda12.4
gpu:
  vendor: nvidia
  family: ampere
constraints:
  disallow:
    serve: []
```

## Layers and Stacks

Layers are reusable intent units. Stacks (usually `kind: stack_recipe`) define ordered layer composition.

### Layer example (`specs/layers/*.yaml`)

```yaml
kind: layer
schema_version: 2
id: fastapi
display_name: "FastAPI API layer"
stack_layer: serving_layer
block_kind: api
components:
  pip:
    - { name: "fastapi", version: "==0.115.*" }
```

### Stack recipe example (`specs/stacks/*.yaml`)

```yaml
kind: stack_recipe
schema_version: 2
id: my_service
display_name: "My Service"
layers: [ubuntu_24_04_runtime, pytorch_core_compute, fastapi]
build_strategy: overlay
components:
  base_role: pytorch
```

### Composition rules

- Layer order matters; later layers win for composable scalar collisions.
- Recipe identity fields (`id`, `display_name`) are authoritative.
- `env` keys dedupe by key; later values win.
- `pip` entries dedupe by package; incompatible constraints fail fast.
- Layer assignment is explicit through `stack_layer`.

Helpful commands:

```bash
stackwarden inspect-layer --id fastapi
stackwarden compose --stack my_service --json
```

## Build Performance (Layered Overlay Strategy)

Use `build_strategy: overlay` for fastest iteration:

- Keep `files.copy` narrow.
- Separate frequently changing app code from slower-changing dependency files.
- Prefer lockfiles and pinned constraints where possible.
- Run `plan` before `ensure` for quick safety checks.

## Dependency Install Modes

### Python (`pip_install_mode`)

| Mode | Behavior |
|------|----------|
| `index` | Standard index installs |
| `wheelhouse_prefer` | Wheelhouse first, index fallback |
| `wheelhouse_only` | Wheelhouse required (`--no-index`) |

### npm (`npm_install_mode`)

| Mode | Behavior |
|------|----------|
| `spec` | Use declared deps |
| `lock_prefer` | Use lockfile if present |
| `lock_only` | Require lockfile |

### apt (`apt_install_mode`)

| Mode | Behavior |
|------|----------|
| `repo` | Standard repo install |
| `pin_prefer` | Repo install with pinning intent |
| `pin_only` | Every apt package must be pinned |

## Tuple Layer (Architecture-Aware Decisions)

Tuple decisions map host/runtime facts to supported implementation paths.

- Source: `specs/rules/tuple_catalog.yaml`
- Mode env var: `STACKWARDEN_TUPLE_LAYER_MODE=off|shadow|warn|enforce`
- Labels include tuple metadata for traceability.

## Drift Detection

Artifacts can be marked stale for reasons including:

- fingerprint mismatch
- base digest change
- template hash change
- stack/profile/layer schema change
- builder version change
- missing expected StackWarden labels

On drift, `ensure` marks old artifacts stale and rebuilds unless `--immutable` is set.

```bash
stackwarden ensure -p dgx_spark -s llm_vllm --immutable
stackwarden catalog stale
```

## Artifact Lifecycle and Operations

Status progression: `planned -> building -> built|failed`, with `built -> stale` when drift is detected.

```bash
stackwarden prune --stale
stackwarden prune --failed
stackwarden prune --all-unused
stackwarden catalog disk-usage
```

The newest `built` artifact per `(profile, stack, variant)` is protected unless `--force` is used.

## Manifest, Repro, and SBOM

After successful builds, StackWarden captures manifest metadata (dependency snapshots, runtime details, install modes).

```bash
stackwarden manifest <tag>
stackwarden repro <artifact-id>
stackwarden sbom <tag> --format spdx-json
```

SBOM generation is best-effort and does not fail artifact status.

## Variant System

Variants support deterministic matrix expansion for stack behavior:

```bash
stackwarden ensure -p dgx_spark -s llm_vllm --var xformers=true --var precision=fp16
```

Variant values are included in fingerprint/tag derivation.

## Registry Policies

Configure allow/deny registries in `~/.config/stackwarden/config.yaml`:

```yaml
registry:
  allow: [nvcr.io, ghcr.io]
  deny: [docker.io/library/randomuser]
```

## Troubleshooting

Start with `stackwarden doctor`.

| Issue | Typical fix |
|-------|-------------|
| Docker not reachable | Start daemon / fix socket perms |
| Buildx unavailable | Install/enable Buildx |
| GPU not visible | Validate drivers + runtime toolkit |
| Arch mismatch | Align profile/daemon arch or expect slower emulation |

## Deprecation Policy

Two-step process:

1. Deprecation window with warnings.
2. Removal window with replacement guidance.

Current deprecations:

| Old | New / Status |
|-----|---------------|
| `stackwarden profiles list` | `stackwarden list profiles` |
| `stackwarden stacks list` | `stackwarden list stacks` |
| `stackwarden layers list` | `stackwarden list layers` |
| `stackwarden catalog build` | `stackwarden ensure` |
| `POST /api/system/detection-hints/remote` | `GET /api/system/detection-hints` |
| `/blocks*` UI routes | Redirected to `/layers*`; compatibility redirect removal scheduled after `2026-12-31` |
