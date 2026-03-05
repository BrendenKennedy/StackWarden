"""Spec snapshot persistence for artifacts.

Every artifact gets ``profile.json``, ``stack.json``, and optionally
``plan.json`` written alongside the manifest so the build is fully
reproducible even if source YAML files change later.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from stackwarden.domain.hashing import canonical_json
from stackwarden.paths import get_artifacts_root

if TYPE_CHECKING:
    from stackwarden.domain.models import Plan, Profile, StackSpec

log = logging.getLogger(__name__)

_FINGERPRINT_RE = re.compile(r"^[a-f0-9]{12,64}$")


def _validate_fingerprint(fingerprint: str) -> None:
    if not _FINGERPRINT_RE.match(fingerprint):
        raise ValueError(f"Invalid fingerprint format: {fingerprint!r}")


def artifact_dir(fingerprint: str) -> Path:
    """Return the artifact directory for a given fingerprint."""
    _validate_fingerprint(fingerprint)
    return get_artifacts_root() / fingerprint


def write_snapshot_files(
    art_dir: Path,
    profile: Profile,
    stack: StackSpec,
    plan: Plan | None = None,
) -> dict[str, Path]:
    """Write canonical JSON snapshots of the resolved profile, stack, and plan.

    The profile and stack must be the exact resolved objects used to compute
    the fingerprint -- not re-loaded from YAML.

    Returns a dict mapping field names to written paths.
    """
    art_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for name, model in [("profile", profile), ("stack", stack)]:
        p = art_dir / f"{name}.json"
        p.write_text(canonical_json(model.model_dump(mode="json")))
        paths[f"{name}_snapshot_path"] = p

    if plan:
        p = art_dir / "plan.json"
        p.write_text(canonical_json(plan.model_dump(mode="json")))
        paths["plan_path"] = p

    return paths


def load_snapshot(art_dir: Path, name: str) -> dict:
    """Load a snapshot JSON file and return the parsed dict."""
    import json

    path = art_dir / f"{name}.json"
    return json.loads(path.read_text())
