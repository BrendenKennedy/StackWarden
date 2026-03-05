# StackWarden

**Deterministic, hardware-aware container builds for ML inference.**

---

## The Problem

You have a diffusion model that runs perfectly on your DGX workstation. Now ship it to three other teams -- one on A100s with CUDA 12.4, one on L40S with CUDA 12.6, and one on a CPU-only staging box. Each team spends a day wrestling with base image versions, driver mismatches, and pip dependency conflicts. Someone pins `torch==2.3.0` to fix one host and silently breaks another. A month later, the base image gets a silent upstream update and nobody notices until inference latency spikes in production.

There is no audit trail, no way to prove two builds are identical, and no single command to answer "what changed?"

## How StackWarden Fixes This

StackWarden is a CLI and web tool that turns the problem into a deterministic pipeline:

- **Profiles describe hosts, not wishes.** A profile captures what hardware you actually have -- GPU family, CUDA version, driver constraints, container runtime -- so the resolver can make safe decisions instead of guessing.
- **Blocks express intent, not implementation.** Select composable blocks (`fastapi`, `vllm`, `triton`) to say *what* your application needs. StackWarden resolves the compatible dependency set for each target host automatically.
- **Layered overlay builds keep rebuilds fast.** Overlay strategy reuses base image layers and copies only declared `files.copy` inputs into an isolated build context, so small source changes avoid expensive full rebuilds.
- **Every build gets a fingerprint.** A SHA-256 hash of all inputs (profile, stack, base image digest, every dependency version, template, builder version) produces a deterministic tag. Same inputs = same tag, always.
- **Drift is detected, not discovered in production.** When an upstream base image changes, a template is modified, or a schema version bumps, StackWarden marks the old artifact `stale` and triggers a rebuild -- or fails hard in CI with `--immutable`.
- **Full provenance from plan to artifact.** Every built image carries OCI labels, a resolved manifest (exact `pip freeze`, `dpkg-query`, `npm ls`), and optional SBOM export. Reproduce any past build with `stackwarden repro`.

## Quick Start

**Prerequisites:** Docker with Buildx. For GPU profiles: NVIDIA Container Toolkit. For SBOM: Docker Desktop (`docker sbom`) or [Syft](https://github.com/anchore/syft). See [docs/reference.md#prerequisites](docs/reference.md#prerequisites).

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Verify your environment
stackwarden doctor

# See what's available
stackwarden list profiles
stackwarden list stacks

# Plan a build (dry run)
stackwarden plan --profile dgx_spark --stack diffusion_fastapi

# Build the image
stackwarden ensure --profile dgx_spark --stack diffusion_fastapi
```

## Documentation

| Topic | Link |
|-------|------|
| **Full doc index** | [docs/README.md](docs/README.md) |
| **Prerequisites** (Docker, Buildx, NVIDIA, SBOM tools) | [docs/reference.md#prerequisites](docs/reference.md#prerequisites) |
| **User reference** (profiles, stacks, blocks, drift, variants, registry policies, troubleshooting) | [docs/reference.md](docs/reference.md) |
| **Layered build performance** (fast rebuild guidance) | [docs/reference.md#build-performance-layered-overlay-strategy](docs/reference.md#build-performance-layered-overlay-strategy) |
| **Composable blocks and wizards** | [docs/cli_wizard_usage.md](docs/cli_wizard_usage.md) |
| **Hardware detection matrix** | [docs/hardware_detection_matrix.md](docs/hardware_detection_matrix.md) |
| **System architecture** | [docs/project-report/02-system-architecture.md](docs/project-report/02-system-architecture.md) |
| **Architecture deep-dive** (full report) | [docs/project-report/README.md](docs/project-report/README.md) |
| **Design philosophy and principles** | [docs/project-report/01-philosophy-and-principles.md](docs/project-report/01-philosophy-and-principles.md) |
| **Intent-first design ADR** | [docs/adr/intent-first-contract.md](docs/adr/intent-first-contract.md) |
| **Web UI architecture** | [docs/project-report/05-web-ui-architecture.md](docs/project-report/05-web-ui-architecture.md) |
| **Glossary and concepts** | [docs/project-report/10-glossary-and-concepts.md](docs/project-report/10-glossary-and-concepts.md) |
| **Onboarding guide** | [docs/project-report/08-onboarding-guide.md](docs/project-report/08-onboarding-guide.md) |
| **Example plans** | [docs/examples/example_plans.md](docs/examples/example_plans.md) |
| **Repository layout** | [docs/repository_layout.md](docs/repository_layout.md) |

## Project Structure

```
packages/stackwarden/   Python package (CLI, domain, resolvers, builders, catalog, web API)
apps/web/               Vue frontend
services/               ML API services (agentic RAG, ASR, diffusion, etc.)
specs/                  Authored profiles, stacks, blocks, rules, configs, and templates (YAML)
docs/                   Architecture, contributor documentation, and examples
tests/                  Backend and contract tests
ops/                    Operational scripts and systemd units
```

For full placement rules, see [docs/repository_layout.md](docs/repository_layout.md).

## Web UI

StackWarden includes a browser-based UI for managing profiles, stacks, blocks, and build artifacts. Start both the backend API and the Vue dev server:

```bash
make dev-api    # Backend API on http://127.0.0.1:8765
make dev-web    # Vue dev server on http://localhost:5173
```

Or bring up both together via the service scripts:

```bash
make services-up
```

## Development

A root `Makefile` provides common tasks. Run `make help` to list all targets.

```bash
make install    # Install Python (editable) + npm dependencies
make test       # Run all tests (Python + Vue)
make lint       # Lint Python source with ruff
make format     # Format Python source with ruff
make typecheck  # Run mypy
make build      # Build Vue frontend for production
make ci         # Run the full CI pipeline locally (lint + test + build)
make clean      # Remove build artifacts and caches
```

## Contributing

Start with the [onboarding guide](docs/project-report/08-onboarding-guide.md) for environment setup, a mental model walkthrough, and suggested first contributions. The [docs index](docs/README.md) has a complete map of all documentation.

## License

This project is licensed under the [MIT License](LICENSE).
