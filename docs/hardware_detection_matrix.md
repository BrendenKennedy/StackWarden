# Hardware Detection Fact Matrix

Source-of-truth coverage for hardware facts used during profile detection and guided profile creation.

## Detection Chain

Detection order (explicit and testable):

1. Bootstrap invariants (`arch`, `os`, `os_family`, `os_version`).
2. Detect execution context (container hints, Docker availability/runtime visibility, command gates).
3. Route by OS family and capability gates:
   - `ubuntu`/`debian` -> Debian/Ubuntu host resource branch.
   - other Linux families -> generic Linux branch.
   - capability-gated probes (for example, `nvidia-smi`, Docker daemon info) run only when available.
4. Merge and normalize fields.
5. Reconcile to catalog IDs and compute quality metrics.

## Fact Coverage

- `arch`
  - Source: `platform.machine()` and Docker daemon `info.Architecture`.
  - Normalization: `x86_64 -> amd64`, `aarch64 -> arm64`.
  - Confidence: `detected`.
  - Profile target: `profile.arch`.

- `os`
  - Source: `platform.system()` and Docker daemon `info.OSType`.
  - Normalization: lowercase (`linux` expected).
  - Confidence: `detected`.
  - Profile target: `profile.os`.

- `os_family`, `os_version`
  - Source: `/etc/os-release` (`ID`, `VERSION_ID`).
  - Normalization: lowercase family, raw version string.
  - Confidence: `detected`.
  - Profile target: `profile.os_family`, `profile.os_version`.

- `container_runtime`
  - Source: Docker daemon runtimes (`nvidia` present or fallback `runc`).
  - Confidence: `detected`.
  - Profile target: `profile.container_runtime`.

- `gpu.vendor`, `gpu.family`, `gpu.compute_capability`, `gpu_model`
  - Source: `nvidia-smi` queries and model-name inference.
  - Normalization:
    - Vendor set to `nvidia` for successful probe.
    - Family inferred from model token heuristics.
    - Model from first detected GPU name.
  - Confidence:
    - `gpu_vendor`: `detected`
    - `gpu_family`: `inferred`
    - `gpu_model`: `detected` when available
    - `compute_capability`: `detected|unknown`
  - Profile target: `profile.gpu.*` and `profile.gpu_devices[*]`.

- `cuda` (`major`, `minor`, `variant`)
  - Source: `nvidia-smi` output token `CUDA Version`.
  - Normalization: `variant=cuda{major}.{minor}`.
  - Confidence: `cuda_runtime` `detected|unknown`.
  - Profile target: `profile.cuda`, `capability_ranges[cuda_runtime]`.

- `driver_version`
  - Source: `nvidia-smi --query-gpu=driver_version`.
  - Confidence: `detected`.
  - Profile target: `profile.host_facts.driver_version`.

- `cpu_model`, `cpu_cores_logical`, `cpu_cores_physical`
  - Source (Ubuntu/Debian): `/proc/cpuinfo` + fallback `lscpu`.
  - Source (generic Linux): `lscpu` + fallback `/proc/cpuinfo`.
  - Fallback: `os.cpu_count()` for logical cores.
  - Normalization: direct extraction; physical cores from `(physical id, core id)` tuples when available.
  - Confidence: `detected|unknown`.
  - Profile target: `profile.host_facts.cpu_*`.

- `memory_gb_total`
  - Source (Ubuntu/Debian): `/proc/meminfo` (`MemTotal`) + fallback `os.sysconf`.
  - Source (generic Linux): `os.sysconf` + fallback `/proc/meminfo`.
  - Normalization: KiB -> GiB rounded to 2 decimals.
  - Confidence: `detected|unknown`.
  - Profile target: `profile.host_facts.memory_gb_total`.

- `disk_gb_total`
  - Source: `disk_usage("/")` + fallback `df -k /`.
  - Normalization: bytes -> GiB rounded to 2 decimals.
  - Confidence: `detected|unknown`.
  - Profile target: `profile.host_facts.disk_gb_total`.

## Catalog Reconciliation Coverage

Detection output is reconciled against `specs/rules/hardware_catalog.yaml` for:

- `arch -> arch_id`
- `os_family -> os_family_id`
- `os_version -> os_version_id`
- `container_runtime -> container_runtime_id`
- `gpu.vendor -> gpu_vendor_id`
- `gpu.family -> gpu_family_id`
- `gpu_model -> gpu_model_id`

Unresolved values are emitted as `unmatched_suggestions` with `{catalog, raw_value, suggested_id}`.

## Acceptance Checklist

- `stackwarden profiles detect --json` returns deterministic field names and confidence keys.
- `/api/system/detection-hints` and CLI detection expose aligned fact surfaces.
- Probe list includes explicit branch/gate diagnostics (`bootstrap_invariants`, `execution_context`, `os_router`).
- `resolved_ids` includes canonical catalog IDs when mappings exist.
- `unmatched_suggestions` captures unmapped tokens for catalog expansion.
- `unknown_rate` tracks unresolved confidence fields.
- Guided profile setup writes host facts into `host_facts` without mixing software-intent fields.
