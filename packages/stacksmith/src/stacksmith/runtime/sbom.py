"""SBOM export — docker sbom with syft fallback.

SBOM generation is auxiliary metadata.  Failures must NEVER mark an
artifact as failed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from stacksmith.domain.manifest import manifest_dir

log = logging.getLogger(__name__)


class SbomUnavailableError(Exception):
    """Raised when no SBOM tool is available."""


def export_sbom(
    tag: str,
    fingerprint: str,
    output_format: str = "spdx-json",
) -> Path:
    """Export an SBOM for the given image tag.

    Tries ``docker sbom`` first, then ``syft``.  Stores the result at
    ``~/.local/share/stacksmith/artifacts/<fingerprint>/sbom.json``.
    """
    out_dir = manifest_dir(fingerprint)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sbom.json"

    if _try_docker_sbom(tag, out_path, output_format):
        return out_path

    if _try_syft(tag, out_path, output_format):
        return out_path

    raise SbomUnavailableError(
        "No SBOM tool available. Install Docker Desktop (docker sbom) "
        "or Anchore Syft (https://github.com/anchore/syft)."
    )


def _try_docker_sbom(tag: str, out_path: Path, fmt: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "sbom", tag, "--format", fmt],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and result.stdout.strip():
            out_path.write_text(result.stdout)
            log.info("SBOM generated via docker sbom")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def _try_syft(tag: str, out_path: Path, fmt: str) -> bool:
    if not shutil.which("syft"):
        return False
    syft_fmt = {"spdx-json": "spdx-json", "cyclonedx-json": "cyclonedx-json"}.get(fmt, fmt)
    try:
        result = subprocess.run(
            ["syft", tag, "-o", syft_fmt],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and result.stdout.strip():
            out_path.write_text(result.stdout)
            log.info("SBOM generated via syft")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False
