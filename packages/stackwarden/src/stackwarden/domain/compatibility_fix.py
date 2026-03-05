"""Analyze build failures and suggest/apply pip compatibility overrides.

When overlay builds fail due to pip dependency conflicts (e.g. NGC base images
pinning setuptools, torch, or protobuf), this module detects the failure type,
suggests fixes, and can apply them to pip_compatibility_overrides.yaml so
retries succeed without user intervention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from stackwarden.config import _rules_dir


# Known package -> suggested version for NGC PyTorch base images.
# Keys are normalized (lowercase, no extras). Values are PEP 440 constraints.
_NGC_PYTORCH_OVERRIDES: dict[str, str] = {
    "vllm": ">=0.8.3,<1.0",
    "tensorboard": ">=2.14,<3.0",
    "tts": ">=0.21,<0.23",
    "setuptools": ">=77",  # Handled by Dockerfile bootstrap; override for completeness
}

# Patterns that indicate a pip compatibility failure (not e.g. OOM or Docker error).
_PIP_CONFLICT_PATTERNS = [
    re.compile(r"ResolutionImpossible", re.I),
    re.compile(r"Cannot install .+ because .+ conflicting", re.I),
    re.compile(r"The conflict is caused by:", re.I),
    re.compile(r"conflicting dependencies", re.I),
    re.compile(r"No matching distribution found", re.I),
]

# Patterns that map to specific package overrides.
_PACKAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(vllm)\b", re.I), "vllm"),
    (re.compile(r"\b(tensorboard)\b", re.I), "tensorboard"),
    (re.compile(r"\b(tts)\b", re.I), "tts"),
    (re.compile(r"\b(setuptools)\b", re.I), "setuptools"),
    (re.compile(r"\b(datasets)\b", re.I), "datasets"),  # dill conflict
    (re.compile(r"\b(dill)\b", re.I), "dill"),
]


@dataclass
class CompatibilityFixResult:
    """Result of analyzing a build failure for compatibility fix applicability."""

    applicable: bool
    message: str
    suggested_overrides: dict[str, str]
    base_image_hint: str = "nvcr.io/nvidia/pytorch"

    def to_dict(self) -> dict[str, Any]:
        return {
            "applicable": self.applicable,
            "message": self.message,
            "suggested_overrides": self.suggested_overrides,
            "base_image_hint": self.base_image_hint,
        }


def analyze_build_failure(
    error_message: str,
    log_content: str | None = None,
    base_image: str | None = None,
) -> CompatibilityFixResult:
    """Analyze a build failure to determine if a pip compatibility fix applies.

    Args:
        error_message: The exception message or error_detail from the failed build.
        log_content: Optional full build log for richer pattern matching.
        base_image: Optional base image used (e.g. nvcr.io/nvidia/pytorch:25.03-py3).

    Returns:
        CompatibilityFixResult with applicable flag, message, and suggested fixes.
    """
    combined = f"{error_message}\n{log_content or ''}"
    combined_lower = combined.lower()

    # Check if this looks like a pip compatibility failure
    is_pip_conflict = any(p.search(combined) for p in _PIP_CONFLICT_PATTERNS)
    if not is_pip_conflict:
        return CompatibilityFixResult(
            applicable=False,
            message="Failure does not appear to be a pip dependency conflict.",
            suggested_overrides={},
        )

    # Check if base image is NGC PyTorch (or we assume it for overlay builds)
    base_hint = "nvcr.io/nvidia/pytorch"
    if base_image and "nvcr.io/nvidia/pytorch" in base_image.lower():
        base_hint = "nvcr.io/nvidia/pytorch"
    elif base_image and "nvidia" in base_image.lower():
        base_hint = base_image.split(":")[0] if ":" in base_image else base_image

    # Detect which packages are involved
    detected: set[str] = set()
    for pattern, pkg in _PACKAGE_PATTERNS:
        if pattern.search(combined):
            detected.add(pkg)

    if not detected:
        return CompatibilityFixResult(
            applicable=True,
            message="Pip conflict detected but no known package override available. "
            "Consider manually adding an entry to specs/rules/pip_compatibility_overrides.yaml",
            suggested_overrides={},
            base_image_hint=base_hint,
        )

    # Build suggested overrides from known mappings
    suggested: dict[str, str] = {}
    for pkg in detected:
        if pkg in _NGC_PYTORCH_OVERRIDES:
            suggested[pkg] = _NGC_PYTORCH_OVERRIDES[pkg]
        elif pkg == "datasets":
            # datasets/dill conflict: relax datasets
            suggested["datasets"] = ">=2.14,<4.0"
        elif pkg == "dill":
            # dill conflict: often from datasets; relax datasets
            suggested["datasets"] = ">=2.14,<4.0"

    if not suggested:
        return CompatibilityFixResult(
            applicable=True,
            message=f"Pip conflict involving {', '.join(sorted(detected))} but no known fix. "
            "Consider manually editing pip_compatibility_overrides.yaml and retrying.",
            suggested_overrides={},
            base_image_hint=base_hint,
        )

    pkg_list = ", ".join(f"{k}={v}" for k, v in sorted(suggested.items()))
    return CompatibilityFixResult(
        applicable=True,
        message=f"Apply pip compatibility overrides: {pkg_list}",
        suggested_overrides=suggested,
        base_image_hint=base_hint,
    )


def apply_compatibility_fix(
    suggested_overrides: dict[str, str],
    base_image_contains: str = "nvcr.io/nvidia/pytorch",
    rules_dir: Path | None = None,
) -> bool:
    """Merge suggested overrides into pip_compatibility_overrides.yaml.

    Finds existing rule matching base_image_contains and merges package overrides.
    Creates new rule if none matches.

    Returns True if the file was modified.
    """
    if rules_dir is None:
        rules_dir = _rules_dir()
    path = rules_dir / "pip_compatibility_overrides.yaml"

    if not path.exists():
        data: dict[str, Any] = {
            "schema_version": 1,
            "revision": 1,
            "overrides": [
                {
                    "when": {"base_image_contains": base_image_contains},
                    "packages": suggested_overrides,
                },
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return True

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    overrides = data.get("overrides", [])
    merged = False

    for rule in overrides:
        when = rule.get("when") or {}
        contains = (when.get("base_image_contains") or "").strip()
        if not contains:
            continue
        # Match when rule targets same base family (one contains the other)
        a, b = base_image_contains.lower(), contains.lower()
        if a not in b and b not in a:
            continue
        packages = rule.get("packages") or {}
        for pkg, version in suggested_overrides.items():
            if pkg not in packages or packages[pkg] != version:
                packages[pkg] = version
                merged = True
        rule["packages"] = packages
        break
    else:
        overrides.append({
            "when": {"base_image_contains": base_image_contains},
            "packages": suggested_overrides,
        })
        merged = True

    if merged:
        data["overrides"] = overrides
        data["revision"] = data.get("revision", 1) + 1
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return merged
