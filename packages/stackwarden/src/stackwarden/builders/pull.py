"""Pull builder — pull a base image and apply StackWarden labels via a thin overlay.

Because Docker does not support adding labels to an already-pulled image
without a build step, we generate a minimal ``FROM base\\nLABEL ...``
Dockerfile and build it.  This keeps label injection consistent with the
overlay builder.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from stackwarden.runtime import buildx

if TYPE_CHECKING:
    from stackwarden.domain.models import Plan, Profile
    from stackwarden.runtime.docker_client import DockerClient

log = logging.getLogger(__name__)


def _split_image_ref(ref: str) -> tuple[str, str]:
    """Split a Docker image reference into (repository, tag).

    Handles registries with ports (e.g. ``myregistry:5000/image:tag``).
    """
    at_idx = ref.find("@")
    if at_idx != -1:
        return ref[:at_idx], ref[at_idx:]

    last_colon = ref.rfind(":")
    last_slash = ref.rfind("/")
    if last_colon > last_slash:
        return ref[:last_colon], ref[last_colon + 1:]
    return ref, "latest"


def build_pull(
    plan: Plan,
    profile: "Profile",
    docker_client: "DockerClient",
) -> str:
    """Pull the base image, then apply StackWarden labels via a thin overlay."""
    base = plan.decision.base_image
    repo, tag = _split_image_ref(base)

    docker_client.pull_image(repo, tag)

    platform = f"{profile.os}/{profile.arch.value}"
    labels = plan.artifact.labels
    buildx_flags = []
    if plan.decision.build_optimization:
        buildx_flags = plan.decision.build_optimization.buildx_flags

    with tempfile.TemporaryDirectory(prefix="stackwarden_pull_") as tmpdir:
        dockerfile = Path(tmpdir) / "Dockerfile"
        dockerfile.write_text(f"FROM {base}\n")

        buildx.build(
            context_dir=tmpdir,
            dockerfile=dockerfile,
            tags=[plan.artifact.tag],
            platform=platform,
            labels=labels,
            extra_flags=buildx_flags,
            load=True,
        )

    return plan.artifact.tag
