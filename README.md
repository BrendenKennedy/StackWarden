# StackWarden

**DGX Spark-first container builds for research teams that need to ship fast.**

---

## Problem This Solves

Teams lose time when ML container builds are passed between machines and environments:

- A stack works on one box, fails on another due to runtime or dependency mismatch.
- Rebuilds are slow because minor app changes invalidate too much build work.
- Upstream changes (base image, templates, package ecosystem) introduce silent drift.
- Nobody can quickly answer what changed between two builds when incidents happen.

StackWarden replaces that with a deterministic, explainable workflow.

## Why Teams Use StackWarden

- **DGX Spark-first fast path.** Start from curated profiles, layers, and stacks built for rapid bring-up.
- **Intent-first resolution.** Declare profile + stack + layers; resolver and compatibility rules derive the implementation path.
- **Fast iteration loops.** Overlay builds and narrow copy context keep rebuilds short for research teams.
- **Deterministic provenance.** Fingerprints, labels, manifests, and catalog history preserve reproducibility.
- **Drift-aware operations.** Detect stale artifacts early and enforce immutable behavior in CI when needed.

## Quick Start

**You'll need:** Docker with Buildx installed. For GPU targets, the NVIDIA Container Toolkit. See the [prerequisites guide](docs/reference.md#prerequisites) for details.

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,wizard,web]"

# Check that your environment is ready
stackwarden doctor

# Browse available profiles and stacks
stackwarden list profiles
stackwarden list stacks
stackwarden list layers

# DGX Spark quick path: preview first, then build
stackwarden plan --profile dgx_spark --stack diffusion_fastapi

# Build the image
stackwarden ensure --profile dgx_spark --stack diffusion_fastapi
```

For research teams that just need results: run `doctor` -> `plan` -> `ensure`.

## Web UI

StackWarden includes a browser UI for profiles, stacks, layers, jobs, and artifact operations.

```bash
make dev-api    # Backend API on http://127.0.0.1:8765
make dev-web    # Vue dev server on http://localhost:5173
```

Or bring up both at once:

```bash
make services-up
```

### Authentication and Credential Recovery

- StackWarden web auth uses a single-admin username/password account with server-side sessions.
- On first launch (no admin account present), the UI shows the initial setup page to create the admin account.
- Protected `/api/*` endpoints require an authenticated session, with only `/api/health` and auth bootstrap/login/status endpoints available pre-login.
- There is no in-app "forgot password" or admin reset path.
- If credentials are lost, the supported recovery is destructive: reinstall or wipe StackWarden app state, then re-run first-time setup.
- Destructive recovery removes existing local StackWarden data (including custom catalog/config state and build history/artifact metadata).

## Where To Go From Here

Depending on what you're trying to do, here's where to look next.

### I just want to use it

| Resource | What you'll find |
|----------|-----------------|
| [Prerequisites](docs/reference.md#prerequisites) | Required and optional software to get started |
| [User Reference](docs/reference.md) | Profiles, stacks, layers, drift detection, variants, and troubleshooting |
| [CLI Wizard Walkthrough](docs/cli_wizard_usage.md) | Interactive commands for creating profiles, layers, and stacks |
| [Example Build Plans](docs/examples/example_plans.md) | Sample `stackwarden plan` outputs for common setups |
| [Hardware Detection Matrix](docs/hardware_detection_matrix.md) | How StackWarden detects your hardware and what it looks for |

### I want to understand how it works under the hood

| Resource | What you'll find |
|----------|-----------------|
| [System Architecture](docs/project-report/02-system-architecture.md) | High-level overview of components and data flow |
| [Design Philosophy](docs/project-report/01-philosophy-and-principles.md) | The principles behind StackWarden's design |
| [Full Architecture Deep-Dive](docs/project-report/README.md) | 10-chapter report covering every layer in detail |
| [Glossary](docs/project-report/10-glossary-and-concepts.md) | Definitions of StackWarden-specific terms |

### I want to contribute

| Resource | What you'll find |
|----------|-----------------|
| [Onboarding Guide](docs/project-report/08-onboarding-guide.md) | First-day setup, mental model, and suggested first contributions |
| [Repository Layout](docs/repository_layout.md) | Directory structure and file placement rules |
| [Testing Strategy](docs/project-report/09-testing-and-quality-strategy.md) | How tests are organized and what to write |
| `make test-stress-e2e` | Repeated CLI+web API end-to-end stress checks for regression discovery |
| [Design Decisions & ADRs](docs/project-report/07-design-decisions-and-adrs.md) | Why things are the way they are |

### I need to run this in CI or production

| Resource | What you'll find |
|----------|-----------------|
| [Prerequisites](docs/reference.md#prerequisites) | Environment requirements for headless and CI setups |
| [Drift Detection](docs/reference.md#drift-detection) | How drift is caught and how `--immutable` mode works |
| [Registry Policies](docs/reference.md#registry-policies) | Configuring trusted registries with allow/deny lists |
| [Build Performance](docs/reference.md#build-performance-layered-overlay-strategy) | Getting the fastest possible incremental rebuilds |

For the complete doc map, see the [documentation index](docs/README.md).

## License

This project is licensed under the [MIT License](LICENSE).
