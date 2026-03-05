# StackWarden

**Stop wasting days getting your ML models to run on someone else's machine.**

---

## Sound Familiar?

Your team just spent weeks training a model. It runs great on your workstation. Everyone's excited. Then you hand it off.

The first team tries to spin it up on their hardware. It crashes on import. Wrong CUDA version. They spend a day digging through forums, swapping base images, and re-installing packages until something works.

The second team picks up your "fixed" container. It won't even start -- turns out the dependency someone pinned to fix the first machine quietly broke compatibility with theirs. Another day gone.

A month goes by. Everything seems stable. Then inference starts crawling in production. Nobody changed any code. Eventually someone discovers that an upstream base image got a silent update that nobody knew about. There was no alert, no log, no way to tell what was different.

Now your team lead is asking a simple question that nobody can answer: *"What changed between the build that worked and the one that doesn't?"*

And through all of this, every time someone tweaks a single line of code or bumps one dependency, the entire container rebuilds from scratch. Twenty minutes of waiting, every single time.

This is the cycle that StackWarden breaks.

## What StackWarden Does For You

StackWarden is a CLI and web tool that takes the guesswork and tribal knowledge out of packaging ML applications into containers.

- **Describe your hardware once, deploy everywhere.** Tell StackWarden what GPUs, drivers, and runtimes each team actually has. It figures out the right set of compatible dependencies for each target -- no more guessing, no more "works on my machine."

- **Say what your app needs, not how to wire it up.** Pick the pieces your application requires -- a serving framework, an inference engine, a set of utilities -- and StackWarden assembles a container that fits. You describe the *what*; it handles the *how*.

- **Small changes rebuild in seconds, not minutes.** Tweak a source file or update a config and only the affected layer rebuilds. No more waiting 20 minutes because you changed one line of Python.

- **Every build gets a fingerprint.** Same inputs always produce the same tag. If two people build from the same configuration, they get identical results. No surprises, no "it worked yesterday."

- **Catch upstream changes before your users do.** When a base image updates, a template drifts, or a dependency shifts, StackWarden flags it immediately. In CI, you can make it fail hard so nothing sneaks into production unnoticed.

- **Reproduce any past build with one command.** Full traceability from the plan that was approved to the artifact that shipped. Months later, you can recreate exactly what ran in production -- no archaeology required.

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

# Preview a build without running it
stackwarden plan --profile dgx_spark --stack diffusion_fastapi

# Build the image
stackwarden ensure --profile dgx_spark --stack diffusion_fastapi
```

## Web UI

StackWarden also includes a browser-based interface for managing profiles, stacks, blocks, and build artifacts.

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
| [User Reference](docs/reference.md) | Profiles, stacks, blocks, drift detection, variants, and troubleshooting |
| [CLI Wizard Walkthrough](docs/cli_wizard_usage.md) | Interactive commands for creating profiles, blocks, and stacks |
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
