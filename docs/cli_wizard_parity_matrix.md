# CLI Wizard Parity Matrix

This matrix defines parity targets between the web wizard flows and the CLI
wizard flows. It is the implementation contract for guided create workflows.

## Profiles

| Web Step | Web Behavior | CLI Parity Target | Source of Truth |
|---|---|---|---|
| hardware | Select hardware/runtime IDs with detection hints | Prompt constrained selects for arch/runtime/OS/GPU IDs; apply detection defaults when available | `stackwarden/web/schemas.py`, `stackwarden/domain/hardware_catalog.py` |
| review | Confirm ID/display and required fields | Validate ID/display and required fields before dry-run/create | `stackwarden/web/routes/meta.py` create contracts + DTO validation |

## Layers

| Web Step | Web Behavior | CLI Parity Target | Source of Truth |
|---|---|---|---|
| preset | Choose category/search/preset/profile mode | Prompt preset from layer catalog and profile mode overlay | `stackwarden/domain/block_catalog.py` |
| runtime | Adjust deps/env/ports/imports | Guided edits via constrained prompts; optional dependency imports from files/text | `stackwarden/web/schemas.py` |
| review | Confirm ID/display and summary | Validate then dry-run preview before write | `stackwarden/application/create_flows.py` |

## Stacks

| Web Step | Web Behavior | CLI Parity Target | Source of Truth |
|---|---|---|---|
| hardware | Select target profile | Prompt profile select when profiles exist | `stackwarden/config.py` profile loaders |
| build_strategy | Explicit strategy decision (separate from layers) | Dedicated step to pick `pull`, `overlay`, or default | `stackwarden/web/routes/meta.py` build strategy enum |
| layers | Select ordered layers by layer, enforce required runtime layer | Layer-by-layer guided picks; require `system_runtime_layer` layer | layer tags + catalog layer metadata |
| review | Compose preview/conflicts + final ID/display | Run compose preview, show conflicts, dry-run YAML, confirm write | `stackwarden/application/create_flows.py` compose + dry-run |

## Shared Rules

- No free-text for enumerated fields.
- Free-text allowed only where needed (`id`, `display_name`, explicit imports).
- CLI always validates through existing request DTOs and create flow functions.
- YAML writes must use existing atomic write path.
- Any intentional web/CLI behavior divergence must be documented in this file.
