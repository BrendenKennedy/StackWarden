"""Overlay builder — thin Dockerfile layered on a base image.

Build context is always an isolated temp directory.  Only declared
``files.copy`` entries are included.  The project root is never used
as a build context.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

from stackwarden.config import templates_roots
from stackwarden.runtime import buildx

if TYPE_CHECKING:
    from stackwarden.domain.models import Plan, Profile, StackSpec
    from stackwarden.runtime.docker_client import DockerClient

log = logging.getLogger(__name__)
_LOCKFILE_INSTALL_COMMANDS = {
    "package-lock.json": "npm ci --no-audit --no-fund",
    "pnpm-lock.yaml": "pnpm install --frozen-lockfile",
    "yarn.lock": "yarn install --frozen-lockfile",
}


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    roots = [str(p) for p in templates_roots() if p.exists()]
    if not roots:
        from stackwarden.config import _DEFAULT_DATA_DIR
        roots = [str(_DEFAULT_DATA_DIR / "templates")]
    return Environment(loader=FileSystemLoader(roots), autoescape=False)


def render_requirements(
    stack: StackSpec,
    dest: Path,
    base_image: str | None = None,
) -> bool:
    """Write requirements.txt from stack pip deps.  Returns True if any deps exist.

    When base_image is provided, pip compatibility overrides are applied so
    package versions are adjusted for known base-image conflicts (e.g. NGC
    PyTorch pins). This enables builds to succeed out of the box.
    """
    if not stack.components.pip:
        return False
    from stackwarden.domain.pip_compatibility import apply_overrides

    pip_deps = stack.components.pip
    if base_image:
        pip_deps = apply_overrides(pip_deps, base_image)

    tmpl = _jinja_env().get_template("requirements.txt.j2")
    content = tmpl.render(pip_deps=pip_deps)
    (dest / "requirements.txt").write_text(content)
    return True


def render_dockerfile(
    plan: Plan,
    stack: StackSpec,
    has_requirements: bool,
    dest: Path,
) -> Path:
    """Render the overlay Dockerfile into *dest* and return its path."""
    from stackwarden.domain.pip_compatibility import get_pip_install_options

    pip_install_options = ""
    if has_requirements and plan.decision.base_image:
        pip_install_options = get_pip_install_options(plan.decision.base_image)

    tmpl = _jinja_env().get_template("Dockerfile.overlay.j2")
    apt_mode = stack.components.apt_install_mode
    apt_constraints = stack.components.apt_constraints or {}
    if apt_mode == "pin_only":
        missing = [pkg for pkg in stack.components.apt if pkg not in apt_constraints]
        if missing:
            raise ValueError(
                "apt_install_mode='pin_only' requires constraints for all apt packages; "
                f"missing: {', '.join(sorted(missing))}"
            )
    apt_install = [
        f"{pkg}{apt_constraints.get(pkg, '')}"
        for pkg in stack.components.apt
    ]
    npm_install_commands = _resolve_npm_install_commands(stack)

    pip_install_mode = stack.components.pip_install_mode
    pip_wheelhouse_path = stack.components.pip_wheelhouse_path
    content = tmpl.render(
        pip_install_options=pip_install_options,
        base_image=plan.decision.base_image,
        labels=plan.artifact.labels,
        apt_packages=apt_install,
        pip_requirements=has_requirements,
        pip_install_mode=pip_install_mode,
        pip_wheelhouse_path=pip_wheelhouse_path,
        npm_install_commands=npm_install_commands,
        copy_items=[{"src": c.src, "dst": c.dst} for c in stack.files.copy_items],
        optimization_env=(plan.decision.build_optimization.optimization_env if plan.decision.build_optimization else {}),
        env=stack.env,
        expose_ports=stack.ports,
        entrypoint_cmd_json=json.dumps(stack.entrypoint.cmd),
    )
    dockerfile_path = dest / "Dockerfile"
    dockerfile_path.write_text(content)
    return dockerfile_path


def _npm_spec_install_commands(stack: StackSpec) -> list[str]:
    cmds: list[str] = []
    for dep in stack.components.npm:
        package_spec = dep.name
        if dep.version_mode == "custom" and dep.version:
            package_spec = f"{package_spec}@{dep.version}"
        if dep.package_manager == "pnpm":
            base_cmd = "pnpm add"
            if dep.install_scope == "dev":
                base_cmd += " -D"
        elif dep.package_manager == "yarn":
            base_cmd = "yarn add"
            if dep.install_scope == "dev":
                base_cmd += " -D"
        else:
            base_cmd = "npm install --no-audit --no-fund"
            base_cmd += " --save-dev" if dep.install_scope == "dev" else " --save"
        cmds.append(f"{base_cmd} {package_spec}")
    return cmds


def _detect_lockfile(stack: StackSpec) -> str | None:
    copied = []
    for item in stack.files.copy_items:
        normalized = item.src.replace("\\", "/").rstrip("/")
        copied.append(normalized.rsplit("/", 1)[-1])
    for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock"):
        if name in copied:
            return name
    return None


def _resolve_npm_install_commands(stack: StackSpec) -> list[str]:
    mode = stack.components.npm_install_mode
    lockfile = _detect_lockfile(stack)
    if mode == "spec":
        return _npm_spec_install_commands(stack)
    if lockfile:
        return [_LOCKFILE_INSTALL_COMMANDS[lockfile]]
    if mode == "lock_only":
        raise ValueError(
            "npm_install_mode='lock_only' requires copying one lockfile: "
            "package-lock.json, pnpm-lock.yaml, or yarn.lock"
        )
    return _npm_spec_install_commands(stack)


def copy_service_files(
    stack: StackSpec,
    dest: Path,
    service_root: Path | None = None,
) -> None:
    """Copy declared files.copy entries into the build context."""
    root = service_root or Path.cwd()
    resolved_root = root.resolve()
    resolved_dest = dest.resolve()
    for item in stack.files.copy_items:
        src = (root / item.src).resolve()
        target = (dest / item.src).resolve()
        if not src.is_relative_to(resolved_root):
            raise ValueError(
                f"Copy source escapes service root: {item.src!r}"
            )
        if not target.is_relative_to(resolved_dest):
            raise ValueError(
                f"Copy target escapes build context: {item.src!r}"
            )
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        elif src.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        else:
            log.warning("Source path does not exist, skipping: %s", src)

    wheelhouse_path = (stack.components.pip_wheelhouse_path or "").strip()
    if stack.components.pip_install_mode != "index" and wheelhouse_path:
        src = (root / wheelhouse_path).resolve()
        target = (dest / wheelhouse_path).resolve()
        if not src.is_relative_to(resolved_root):
            raise ValueError(
                f"Wheelhouse path escapes service root: {wheelhouse_path!r}"
            )
        if not target.is_relative_to(resolved_dest):
            raise ValueError(
                f"Wheelhouse target escapes build context: {wheelhouse_path!r}"
            )
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        elif src.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        else:
            raise ValueError(f"Declared pip_wheelhouse_path does not exist: {wheelhouse_path!r}")


def build_overlay(
    plan: Plan,
    stack: StackSpec,
    profile: "Profile",
    docker_client: "DockerClient",
    service_root: Path | None = None,
) -> str:
    """Build an overlay image in an isolated temp context.  Returns image tag."""
    platform = f"{profile.os}/{profile.arch.value}"

    with tempfile.TemporaryDirectory(prefix="stackwarden_") as tmpdir:
        ctx = Path(tmpdir)

        base_image = plan.decision.base_image if plan.decision else ""
        has_req = render_requirements(stack, ctx, base_image=base_image)
        dockerfile = render_dockerfile(plan, stack, has_req, ctx)
        copy_service_files(stack, ctx, service_root)

        log.info("Building overlay in isolated context: %s", ctx)

        overlay_step = next(
            (s for s in plan.steps if s.type == "build_overlay"),
            None,
        )
        tags = overlay_step.tags if overlay_step else [plan.artifact.tag]
        labels = overlay_step.labels if overlay_step else plan.artifact.labels
        build_args = overlay_step.build_args if overlay_step else {}
        buildx_flags = overlay_step.buildx_flags if overlay_step else []

        buildx.build(
            context_dir=ctx,
            dockerfile=dockerfile,
            tags=tags,
            platform=platform,
            build_args=build_args,
            labels=labels,
            extra_flags=buildx_flags,
            load=True,
        )

    return plan.artifact.tag
