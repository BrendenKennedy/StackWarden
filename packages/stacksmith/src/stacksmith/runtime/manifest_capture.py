"""Post-build manifest capture — exec into container to snapshot installed packages."""

from __future__ import annotations

import logging
import json
import subprocess
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from stacksmith.domain.manifest import ResolvedManifest

if TYPE_CHECKING:
    from stacksmith.domain.models import Plan, Profile, StackSpec

log = logging.getLogger(__name__)


def _run_in_container(tag: str, cmd: list[str], *, timeout: int = 60) -> str | None:
    """Run a command inside a disposable container, return stdout or None on failure."""
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=512m",
                "--cpus=1",
                "--read-only",
                "--security-opt=no-new-privileges",
                "--entrypoint", "",
                tag, *cmd,
            ],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        log.debug("Container command %s exited %d: %s", cmd, result.returncode, result.stderr)
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.debug("Container command %s failed: %s", cmd, exc)
        return None


def capture_manifest(
    tag: str,
    profile: Profile,
    stack: StackSpec,
    plan: Plan,
    *,
    variants: dict[str, str] | None = None,
) -> ResolvedManifest:
    """Capture a resolved manifest by introspecting a built container image."""
    python_version = (_run_in_container(tag, ["python", "--version"]) or "").removeprefix("Python ").strip()

    pip_raw = _run_in_container(tag, ["python", "-m", "pip", "freeze"])
    pip_freeze = [line for line in (pip_raw or "").splitlines() if line.strip()]

    apt_raw = _run_in_container(
        tag, ["dpkg-query", "-W", "-f", "${Package}=${Version}\n"]
    )
    if apt_raw:
        apt_packages = [line for line in apt_raw.splitlines() if line.strip()]
    else:
        log.info("dpkg-query unavailable (non-debian base?) — skipping apt capture")
        apt_packages = []

    npm_packages: list[str] = []
    npm_raw = _run_in_container(
        tag,
        [
            "sh",
            "-lc",
            "if command -v npm >/dev/null 2>&1; then npm ls --json --depth=0 2>/dev/null || true; fi",
        ],
    )
    if npm_raw:
        try:
            npm_json = json.loads(npm_raw)
            deps = npm_json.get("dependencies", {}) if isinstance(npm_json, dict) else {}
            if isinstance(deps, dict):
                npm_packages = sorted(
                    [
                        f"{name}@{meta.get('version')}"
                        for name, meta in deps.items()
                        if isinstance(meta, dict) and meta.get("version")
                    ]
                )
        except Exception:
            log.debug("Failed to parse npm ls output for %s", tag)

    return ResolvedManifest(
        profile_id=plan.profile_id,
        stack_id=plan.stack_id,
        fingerprint=plan.artifact.fingerprint,
        base_image=plan.decision.base_image,
        base_digest=plan.decision.base_digest,
        python_version=python_version,
        pip_freeze=pip_freeze,
        pip_install_mode=stack.components.pip_install_mode,
        pip_wheelhouse_path=stack.components.pip_wheelhouse_path,
        npm_install_mode=stack.components.npm_install_mode,
        apt_install_mode=stack.components.apt_install_mode,
        tuple_id=plan.artifact.labels.get("stacksmith.tuple_id", ""),
        tuple_status=plan.artifact.labels.get("stacksmith.tuple_status", ""),
        tuple_mode=plan.artifact.labels.get("stacksmith.tuple_mode", ""),
        apt_packages=apt_packages,
        npm_packages=npm_packages,
        env=list(stack.env),
        entrypoint=list(stack.entrypoint.cmd),
        variant_overrides=variants or {},
        created_at=datetime.now(timezone.utc).isoformat(),
    )
