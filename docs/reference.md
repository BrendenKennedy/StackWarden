# StackWarden Reference Guide

This document consolidates detailed reference material for StackWarden users and operators. For architecture and contributor-oriented documentation, see the [project report](project-report/README.md).

## Prerequisites

StackWarden depends on the following supporting software. Run `stackwarden doctor` to verify your environment.

### Required

| Software | Purpose | Install |
|----------|---------|--------|
| **Docker** | Image builds, container runtime | [docker.com](https://docs.docker.com/get-docker/) |
| **Docker Buildx** | Multi-stage and overlay builds | Usually bundled with Docker; `docker buildx version` to verify |

### Optional (GPU workflows)

| Software | Purpose | Install |
|----------|---------|--------|
| **NVIDIA Container Toolkit** | GPU access in containers (`nvidia` runtime) | [NVIDIA docs](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) |

### Optional (SBOM export)

SBOM (Software Bill of Materials) is generated automatically after builds when a tool is available. Without one, the SBOM tab in the artifact view will show "SBOM not generated."

| Software | Purpose | Install |
|----------|---------|--------|
| **Docker Desktop** (`docker sbom`) | SBOM via built-in `docker sbom` | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes `docker sbom`) |
| **Syft** | Standalone SBOM tool (Linux, no Docker Desktop) | `curl -sSfL https://get.anchore.io/syft \| sh -s -- -b ~/.local/bin` |

Ensure `~/.local/bin` is in your `PATH` if installing Syft to that location.

## Adding Profiles

Profiles are host descriptors that capture detected host/runtime facts and compatibility restrictions. They are not the place to declare desired software functionality -- that intent belongs in stack block selection.

### Guided setup (Web UI)

Open **Create Profile** and click **Guided Setup** to launch the modal wizard.

- The wizard runs host detection against the **StackWarden server host** (not the browser machine).
- Detection is best-effort and always overrideable before writing.
- Required fields are validated before write. The flow uses dry-run + confirm-write.
- If metadata fails to load, verify backend availability: `curl http://127.0.0.1:8765/api/health`
- For full triage, run `python ops/scripts/diagnose_metadata.py`.

API equivalents:

- `GET /api/system/detection-hints` -- server-host prefill hints.
- `GET /api/meta/create-contracts` -- required-field and constraint metadata.

See also: [hardware detection matrix](hardware_detection_matrix.md).

### Profile YAML format

Create a YAML file in `specs/profiles/`:

```yaml
schema_version: 1
id: my_workstation
display_name: "My Workstation"
arch: amd64
os: linux
container_runtime: nvidia
cuda:
  major: 12
  minor: 4
  variant: "cuda12.4"
gpu:
  vendor: nvidia
  family: "ampere"
constraints:
  disallow:
    serve: []
  require:
    env: [NVIDIA_VISIBLE_DEVICES]
base_candidates:
  - name: "nvcr.io/nvidia/pytorch"
    tags: ["24.06-py3"]
    score_bias: 100
defaults:
  python: "3.10"
  workdir: "/workspace"
```

Verify with: `stackwarden list profiles`

## Adding Stacks

Stacks are the primary user intent surface. In blocks-first mode, select and order blocks to express what the application needs, then let resolver logic derive compatible implementation details.

Create a YAML file in `specs/stacks/`:

```yaml
schema_version: 1
kind: stack_recipe
id: my_service
display_name: "My Service"
blocks: [fastapi, vllm]
build_strategy: overlay
components:
  base_role: pytorch
files:
  copy:
    - { src: "services/my_service/", dst: "/app" }
```

## Composable Blocks

Define reusable stack blocks in `specs/blocks/`:

```yaml
kind: block
schema_version: 1
id: fastapi
display_name: "FastAPI API layer"
block_kind: api
components:
  pip:
    - { name: "fastapi", version: "==0.115.*" }
    - { name: "uvicorn", version: "[standard]==0.30.*" }
ports: [8000]
```

Create a recipe stack that composes blocks:

```yaml
kind: stack_recipe
schema_version: 1
id: llm_fastapi_blocks
display_name: "LLM + FastAPI (composed blocks)"
blocks: [fastapi, triton]
build_strategy: overlay
components:
  base_role: pytorch
```

### Merge and precedence rules

- Recipe-owned identity fields are authoritative: `id`, `display_name`.
- Block order matters: later blocks override earlier blocks for composable scalars.
- Recipe overrides apply last.
- `env` entries are deduped by key; later values win.
- `pip` dependencies are deduped by package name; incompatible constraints fail fast.
- V1 does not support transitive block includes.

### CLI commands

```bash
stackwarden inspect-block --id fastapi
stackwarden compose --stack llm_fastapi_blocks --json
```

### Web UI / API

- Create block: `/blocks?create=1`
- Create stack (recipe flow): `/stacks?create=1`
- API: `GET /api/blocks`, `POST /api/blocks`, `POST /api/blocks/dry-run`, `POST /api/stacks/compose`

### Block preset taxonomy

Presets are categorized for ML inference workflows:

- **Baseline**: `llm_serving`, `diffusion`, `vision_inference`, `speech_audio`, `data_rag`
- **Platform**: `agentic_workflows`, `inference_optimization`, `api_app`, `observability`, `infra`
- **Pilot**: `robotics_edge`, `training` (advanced/non-default)

Category and preset IDs must stay stable once published; new entries should be additive.

## Architecture-Aware Tuple Layer

The tuple decision layer resolves hardware/runtime facts into a supported implementation path.

- **Input facts**: `arch`, `os_family_id`, `os_version_id`, `container_runtime`, `gpu_vendor_id`, optional `gpu_family_id` and CUDA/driver windows.
- **Source of truth**: `specs/rules/tuple_catalog.yaml`
- **Outputs**: structured `tuple_decision` in compatibility and plan previews, plus labels on built artifacts.

### Rollout control

Set `STACKWARDEN_TUPLE_LAYER_MODE` to: `off`, `shadow`, `warn`, or `enforce` (default).

Recommended rollout: `shadow` -> `warn` -> `enforce`.

### Tuple provenance

Resolver writes `stackwarden.tuple_id`, `stackwarden.tuple_status`, and `stackwarden.tuple_mode` labels. Manifest capture persists these for repro and verification.

## Dependency Install Modes

### Python wheelhouse

Control pip source policy at stack/block level via `pip_install_mode`:

| Mode | Behavior |
|------|----------|
| `index` (default) | Install from standard pip indexes |
| `wheelhouse_prefer` | `--find-links <path>` with index fallback |
| `wheelhouse_only` | `--no-index --find-links <path>`; fail if missing |

`pip_wheelhouse_path` must be a workspace-relative path and is required for wheelhouse modes.

**Operational guidance**: Start with `wheelhouse_prefer` on canary stacks, then promote stable tuples to `wheelhouse_only`.

### npm lockfile

Control lockfile policy via `npm_install_mode`:

| Mode | Behavior |
|------|----------|
| `spec` (default) | Install from declared `components.npm` |
| `lock_prefer` | Install from lockfile if present, otherwise declared deps |
| `lock_only` | Require one copied lockfile; install from lockfile only |

Supported lockfiles: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`. Include the lockfile in `files.copy`.

### apt version pinning

Control apt pin policy via `apt_install_mode`:

| Mode | Behavior |
|------|----------|
| `repo` (default) | Install from repo; optional `apt_constraints` applied |
| `pin_prefer` | Same as `repo` but documents intent to pin |
| `pin_only` | Require `apt_constraints` for every `components.apt` package |

`apt_constraints` entries are appended to package names (e.g. `curl: "=8.5.0-1ubuntu1"`).

## Build Performance (Layered Overlay Strategy)

StackWarden is designed for fast incremental rebuilds when you use `build_strategy: overlay`.

### How layering stays fast

- Overlay builds start from a resolved base image and add only your declared layers.
- Build context is isolated and includes only declared `files.copy` sources (not the full repo), which reduces context upload and cache invalidation.
- Dependency policy modes (`pip_install_mode`, `npm_install_mode`, `apt_install_mode`) let you keep installs deterministic and cache-friendly.
- Lockfile-based npm installs (`lock_prefer` / `lock_only`) and wheelhouse modes can reduce network and dependency resolution overhead during rebuilds.

### Practical optimization checklist

- Keep `files.copy` narrow. Copy only the directories/files required by the stack.
- Put frequently changing app code in separate copied paths from rarely changing dependency descriptors.
- Prefer lockfiles and pinned constraints for stable layer cache reuse.
- Use `stackwarden plan` first to validate intended steps before running full builds.
- Use `stackwarden ensure --immutable` in CI to fail fast on drift instead of silently rebuilding unexpectedly.

### Example: cache-friendly stack snippet

```yaml
kind: stack_recipe
schema_version: 1
id: my_service_fast
build_strategy: overlay
files:
  copy:
    - { src: "services/my_service/", dst: "/app" }
    - { src: "apps/web/package-lock.json", dst: "/app/package-lock.json" }
```

## Drift Detection

An artifact is marked stale if any of these conditions are true:

1. **Fingerprint mismatch** -- embedded label differs from expected value.
2. **Base digest changed** -- upstream base image was updated.
3. **Template hash changed** -- Dockerfile template was modified.
4. **Stack schema version changed** -- stack spec schema was bumped.
5. **Profile schema version changed** -- profile schema was bumped.
6. **Builder version changed** -- StackWarden version used to build differs from current.

When drift is detected during `ensure`, the old artifact is marked `stale` and a rebuild is triggered. Use `--immutable` to fail instead (important for CI).

```bash
stackwarden ensure -p dgx_spark -s llm_vllm --immutable
stackwarden catalog stale
```

## Artifact Lifecycle

Status progression: `planned` -> `building` -> `built` (or `failed`). A `built` artifact can transition to `stale` when drift is detected.

### Pruning

```bash
stackwarden prune --stale         # Remove stale artifacts + images
stackwarden prune --failed        # Remove failed artifacts
stackwarden prune --all-unused    # Remove all non-newest artifacts
stackwarden prune --all-unused --force  # Include newest stable
```

The newest `built` artifact per (profile, stack, variant) is protected unless `--force` is used.

### Disk usage

```bash
stackwarden catalog disk-usage
```

## Manifest and Reproducible Builds

After every successful build, StackWarden captures a resolved manifest:

- `pip freeze` output (pinned versions)
- `dpkg-query` package list (Debian-based images)
- `npm ls --depth=0` snapshot (when available)
- Selected policy modes (`pip_install_mode`, `npm_install_mode`, `apt_install_mode`)
- Python version, environment variables, and entrypoint

```bash
stackwarden manifest <tag>
stackwarden repro <artifact-id>
```

The `repro` command creates a synthetic stack spec with exact versions, producing a distinct fingerprint to avoid tag collision with the original.

## SBOM Export

```bash
stackwarden sbom <tag> --format spdx-json
stackwarden sbom <tag> --format cyclonedx-json
```

StackWarden tries `docker sbom` first (Docker Desktop), then falls back to [Syft](https://github.com/anchore/syft). SBOM is also generated automatically after each successful build when a tool is available. SBOM generation is auxiliary -- failures never affect artifact status.

See [Prerequisites](#prerequisites) for SBOM tool installation.

## Variant System

Stacks can declare variants for controlled matrix expansion:

```yaml
variants:
  xformers:
    type: bool
    default: false
  precision:
    type: enum
    options: [fp16, bf16, fp32]
    default: bf16
```

```bash
stackwarden ensure -p dgx_spark -s llm_vllm --var xformers=true --var precision=fp16
```

Variant values are included in the fingerprint, so different combinations produce different tags. Unknown variant keys are rejected.

## Registry Policies

Configure trusted registries in `~/.config/stackwarden/config.yaml`:

```yaml
registry:
  allow:
    - nvcr.io
    - ghcr.io
  deny:
    - docker.io/library/randomuser
```

Denied registries are rejected. If an allow list is configured, only listed registries are permitted. Base images referenced without a digest trigger a reproducibility warning.

## Fingerprinting

StackWarden generates a deterministic SHA-256 fingerprint from:

- Profile ID, architecture, CUDA variant
- Base image name and digest
- Resolved build strategy and composed runtime shape
- All pip/npm/apt dependencies (sorted, normalized)
- Install modes (`pip_install_mode`, `npm_install_mode`, `apt_install_mode`)
- Environment variables, ports, copy items (all sorted)
- Dockerfile template hash and template version
- Builder version (`stackwarden.__version__`)
- Variant overrides (sorted keys, stringified values)

Tag format: `local/stackwarden:{stack}-{profile}-{cuda}-{serve}-{api}-{first_12_chars_of_hash}`

Same inputs always produce the same tag. Every image gets OCI labels embedding the full fingerprint, profile, stack, and base digest. Manually retagged images are detected as stale.

## License Warnings

StackWarden includes a best-effort SPDX license mapping in `packages/stackwarden/src/stackwarden/licenses/spdx_map.yaml`.

| Severity | Meaning | Action |
|----------|---------|--------|
| `ok` | Permissive (MIT, Apache-2.0, BSD) | No action needed |
| `review` | Copyleft or ambiguous | Review before redistribution |
| `restricted` | Proprietary EULA or redistribution-limited | Build blocked unless `--allow-restricted` |

**This is not legal advice.** Consult your legal team for redistribution decisions.

## Troubleshooting

Run `stackwarden doctor` to diagnose issues:

| Issue | Fix |
|-------|-----|
| Docker daemon not reachable | Start Docker or check socket permissions |
| Buildx not available | Install Docker Buildx plugin |
| nvidia-container-runtime not found | Install the NVIDIA Container Toolkit |
| GPU not visible | Check NVIDIA drivers and `NVIDIA_VISIBLE_DEVICES` |
| NGC_API_KEY not set | Export `NGC_API_KEY` for NGC container images |
| Architecture mismatch | Docker daemon arch differs from profile; QEMU builds will be slow |

## Deprecation Policy

StackWarden follows a two-step deprecation process:

1. **Deprecation window** (at least one release): old surfaces remain functional with CLI/runtime warnings.
2. **Removal window**: deprecated surfaces are removed; release notes list exact replacements.

Current deprecations:

| Old | New |
|-----|-----|
| `stackwarden profiles list` | `stackwarden list profiles` |
| `stackwarden stacks list` | `stackwarden list stacks` |
| `stackwarden blocks list` | `stackwarden list blocks` |
| `stackwarden catalog build` | `stackwarden ensure` |
| `POST /api/system/detection-hints/remote` | `GET /api/system/detection-hints` |
