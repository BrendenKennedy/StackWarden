"""Compatibility rules evaluated during resolution.

Each check function returns a list of issue strings.  An empty list means
the check passed.  Issues prefixed with ``ERROR:`` are fatal; others are
warnings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stackwarden.domain.models import Profile, StackSpec

_ARM64_PROBLEMATIC_PACKAGES = {
    "xformers": "xformers has limited ARM64 support; torch SDPA will be used instead",
    "tensorrt": "TensorRT wheels are x86-only; use TRT inside the NGC base image",
    "tensorrt_llm": "TensorRT-LLM is x86-only in most releases",
}


def check_arch_compatibility(profile: Profile, stack: StackSpec) -> list[str]:
    """Warn about packages known to be problematic on the target architecture."""
    issues: list[str] = []
    if profile.arch.value == "arm64":
        for dep in stack.components.pip:
            msg = _ARM64_PROBLEMATIC_PACKAGES.get(dep.name)
            if msg:
                issues.append(msg)
    return issues


def check_serve_disallowed(profile: Profile, stack: StackSpec) -> list[str]:
    """Return errors if the profile explicitly disallows the stack's serve type."""
    issues: list[str] = []
    disallowed = profile.constraints.disallow.get("serve", [])
    if stack.serve.value in disallowed:
        issues.append(
            f"ERROR: serve type '{stack.serve.value}' is disallowed by profile '{profile.id}'"
        )
    return issues


def check_required_capabilities(profile: Profile, stack: StackSpec) -> list[str]:
    """Warn if the stack references capabilities the profile does not advertise.

    Currently this is advisory — stacks don't declare required capabilities
    directly, but we check the serve layer against known requirements.
    """
    issues: list[str] = []
    serve_capability_map: dict[str, list[str]] = {
        "triton": ["cuda"],
        "vllm": ["cuda"],
    }
    effective_caps = set(profile.derived_capabilities or [])
    if profile.cuda is not None and profile.cuda.major > 0:
        effective_caps.add("cuda")
    if profile.container_runtime.value.lower() == "nvidia":
        effective_caps.add("cuda")
    required = serve_capability_map.get(stack.serve.value, [])
    for cap in required:
        if cap not in effective_caps:
            issues.append(
                f"ERROR: serve type '{stack.serve.value}' requires capability "
                f"'{cap}' not available from profile facts/derived capabilities for profile '{profile.id}'"
            )
    return issues


def evaluate_all(profile: Profile, stack: StackSpec) -> tuple[list[str], list[str]]:
    """Run all rules.  Returns ``(warnings, errors)``."""
    all_issues = (
        check_arch_compatibility(profile, stack)
        + check_serve_disallowed(profile, stack)
        + check_required_capabilities(profile, stack)
    )
    errors = [i.removeprefix("ERROR: ") for i in all_issues if i.startswith("ERROR:")]
    warnings = [i for i in all_issues if not i.startswith("ERROR:")]
    return warnings, errors
