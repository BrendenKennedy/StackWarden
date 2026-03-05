"""Deterministic fingerprinting and tag generation.

All hash inputs are normalized and sorted before hashing to guarantee that
identical logical inputs always produce the same fingerprint, regardless of
field ordering in the source YAML.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from stackwarden import __version__ as _builder_version

if TYPE_CHECKING:
    from stackwarden.domain.models import Profile, StackSpec


def _normalize_version(v: str) -> str:
    """Collapse whitespace in version specifiers so ``>= 1.0`` and ``>=1.0`` hash identically."""
    return re.sub(r"\s+", "", v.strip())


def canonical_json(obj: dict) -> str:
    """Stable JSON: sorted keys, compact separators.

    Used by both fingerprinting and snapshot serialization so the two
    can never diverge on formatting.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def canonicalize(
    profile: Profile,
    stack: StackSpec,
    base_image: str,
    base_digest: str | None = None,
    template_hash: str | None = None,
    *,
    variants: dict[str, str] | None = None,
    builder_version_override: str | None = None,
) -> str:
    """Build a canonical JSON string from plan inputs.

    Lists are sorted, whitespace normalized, keys ordered deterministically.
    Variant values are stringified and sorted by key before inclusion.

    *builder_version_override* lets callers (e.g. ``verify``) replay a
    fingerprint that was computed with an older StackWarden version.
    """
    pip_entries = sorted(
        [{"name": p.name, "version": _normalize_version(p.version)} for p in stack.components.pip],
        key=lambda e: e["name"],
    )
    npm_entries = sorted(
        [
            {
                "name": n.name,
                "version": _normalize_version(n.version),
                "version_mode": n.version_mode,
                "package_manager": n.package_manager,
                "install_scope": n.install_scope,
            }
            for n in stack.components.npm
        ],
        key=lambda e: (e["name"], e["package_manager"], e["install_scope"]),
    )
    apt_entries = sorted(stack.components.apt)
    apt_constraints = dict(sorted(stack.components.apt_constraints.items()))
    env_entries = sorted(stack.env)
    port_entries = sorted(stack.ports)

    copy_entries = sorted(
        [{"dst": c.dst, "src": c.src} for c in stack.files.copy_items],
        key=lambda e: e["src"],
    )

    normalized_variants = {k: str(v) for k, v in sorted((variants or {}).items())}

    cuda_variant = profile.cuda.variant if profile.cuda else "none"
    payload = {
        "base_digest": base_digest or "",
        "base_image": base_image,
        "builder_version": builder_version_override or _builder_version,
        "copy_items": copy_entries,
        "profile": {
            "arch": profile.arch.value,
            "cuda_variant": cuda_variant,
            "id": profile.id,
        },
        "stack": {
            "api": stack.api.value,
            "apt": apt_entries,
            "apt_constraints": apt_constraints,
            "apt_install_mode": stack.components.apt_install_mode,
            "base_role": stack.components.base_role,
            "build_strategy": stack.build_strategy.value,
            "env": env_entries,
            "id": stack.id,
            "npm": npm_entries,
            "npm_install_mode": stack.components.npm_install_mode,
            "pip": pip_entries,
            "pip_install_mode": stack.components.pip_install_mode,
            "pip_wheelhouse_path": stack.components.pip_wheelhouse_path,
            "ports": port_entries,
            "serve": stack.serve.value,
            "task": stack.task.value,
            "policy_overrides": dict(sorted((stack.policy_overrides or {}).items())),
        },
        "template_hash": template_hash or "",
        "variants": normalized_variants,
    }

    return canonical_json(payload)


def fingerprint(
    profile: Profile,
    stack: StackSpec,
    base_image: str,
    base_digest: str | None = None,
    template_hash: str | None = None,
    *,
    variants: dict[str, str] | None = None,
    builder_version_override: str | None = None,
) -> str:
    """Return a hex SHA-256 fingerprint of the canonical plan inputs."""
    canon = canonicalize(
        profile, stack, base_image, base_digest, template_hash,
        variants=variants,
        builder_version_override=builder_version_override,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def compute_template_hash(template_path: Path) -> str:
    """SHA-256 of the template content, excluding the ``stackwarden_template_hash=``
    line to avoid a circular dependency."""
    lines = template_path.read_text().splitlines(keepends=True)
    filtered = [line for line in lines if not line.strip().startswith("# stackwarden_template_hash=")]
    return hashlib.sha256("".join(filtered).encode("utf-8")).hexdigest()


def extract_template_version(template_path: Path) -> int:
    """Parse ``# stackwarden_template_version=N`` from the first lines of a template."""
    for line in template_path.read_text().splitlines()[:5]:
        m = re.match(r"^#\s*stackwarden_template_version\s*=\s*(\d+)", line)
        if m:
            return int(m.group(1))
    return 0


def generate_tag(
    stack: StackSpec,
    profile: Profile,
    fp: str,
) -> str:
    """Produce a deterministic image tag.

    Format: ``local/stackwarden:{stack}-{profile}-{cuda}-{serve}-{api}-{h12}``
    """
    h12 = fp[:12]
    cuda_variant = profile.cuda.variant if profile.cuda else "nocuda"
    parts = [
        stack.id,
        profile.id,
        cuda_variant,
        stack.serve.value,
        stack.api.value,
        h12,
    ]
    return "local/stackwarden:" + "-".join(parts)
