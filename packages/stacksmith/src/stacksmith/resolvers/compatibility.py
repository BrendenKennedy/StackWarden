"""Deterministic compatibility evaluation for profile + stack (+blocks)."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from stacksmith.config import tuple_layer_mode
from stacksmith.domain.tuple_catalog import SupportedTuple, TupleCatalog, load_tuple_catalog
from stacksmith.domain.models import BlockSpec, CompatibilityIssue, CompatibilityReport, Profile, StackSpec
from stacksmith.resolvers.rule_catalog import CompatibilityRule, CompatibilityRuleCatalog, load_rule_catalog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Req:
    block_id: str
    key: str
    value: object


def _to_float(v: object) -> float | None:
    try:
        if v is None:
            return None
        return float(str(v))
    except (TypeError, ValueError):
        return None


def _requirement_issue(
    req: _Req,
    *,
    code: str,
    message: str,
    rule_id: str,
    field: str,
    fix_hint: str | None = None,
    confidence_context: dict[str, str] | None = None,
) -> CompatibilityIssue:
    return CompatibilityIssue(
        code=code,
        severity="error",
        message=message,
        rule_id=rule_id,
        rule_version=1,
        source=req.block_id,
        field=field,
        fix_hint=fix_hint,
        confidence_context=confidence_context or {},
    )


def _handle_arch(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    if str(req.value) == profile.arch.value:
        return []
    return [
        _requirement_issue(
            req,
            code="ARCH_MISMATCH",
            message=f"Block '{req.block_id}' requires arch '{req.value}', profile is '{profile.arch.value}'",
            rule_id="block-requires-arch",
            field=f"requires.{req.key}",
        )
    ]


def _handle_os(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    if str(req.value).lower() == profile.os.lower():
        return []
    return [
        _requirement_issue(
            req,
            code="OS_MISMATCH",
            message=f"Block '{req.block_id}' requires os '{req.value}', profile is '{profile.os}'",
            rule_id="block-requires-os",
            field="requires.os",
        )
    ]


def _handle_os_family(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    actual = (profile.os_family_id or profile.os_family or profile.os).lower()
    expected = str(req.value).lower()
    if not actual or actual == expected:
        return []
    return [
        _requirement_issue(
            req,
            code="OS_FAMILY_MISMATCH",
            message=f"Block '{req.block_id}' requires os_family_id '{expected}', profile has '{actual}'",
            rule_id="block-requires-os-family-id",
            field="requires.os_family_id",
        )
    ]


def _handle_os_version(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    actual = (profile.os_version_id or profile.os_version or "").lower()
    expected = str(req.value).lower()
    if not actual or actual == expected:
        return []
    return [
        _requirement_issue(
            req,
            code="OS_VERSION_MISMATCH",
            message=f"Block '{req.block_id}' requires os_version_id '{expected}', profile has '{actual}'",
            rule_id="block-requires-os-version-id",
            field="requires.os_version_id",
        )
    ]


def _handle_gpu_vendor(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    actual = (profile.gpu.vendor_id or profile.gpu.vendor or "").lower()
    expected = str(req.value).lower()
    if not actual or actual == expected:
        return []
    return [
        _requirement_issue(
            req,
            code="GPU_VENDOR_MISMATCH",
            message=f"Block '{req.block_id}' requires gpu vendor '{expected}', profile has '{actual}'",
            rule_id=f"block-requires-{req.key.replace('_', '-')}",
            field=f"requires.{req.key}",
        )
    ]


def _handle_gpu_family(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    actual = (profile.gpu.family_id or profile.gpu.family or "").lower()
    expected = str(req.value).lower()
    if not actual or actual == expected:
        return []
    return [
        _requirement_issue(
            req,
            code="GPU_FAMILY_MISMATCH",
            message=f"Block '{req.block_id}' requires gpu family '{expected}', profile has '{actual}'",
            rule_id="block-requires-gpu-family-id",
            field="requires.gpu_family_id",
        )
    ]


def _handle_runtime(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    expected = str(req.value).lower()
    actual = profile.container_runtime.value.lower()
    if actual == expected:
        return []
    return [
        _requirement_issue(
            req,
            code="RUNTIME_MISMATCH",
            message=f"Block '{req.block_id}' requires runtime '{expected}', profile has '{actual}'",
            rule_id="block-requires-container-runtime",
            field="requires.container_runtime",
        )
    ]


def _handle_driver_min(req: _Req, profile: Profile, field_conf: dict[str, str]) -> list[CompatibilityIssue]:
    have = _to_float(profile.host_facts.driver_version)
    need = _to_float(req.value)
    if have is None or need is None or have >= need:
        return []
    return [
        _requirement_issue(
            req,
            code="DRIVER_TOO_OLD",
            message=f"Block '{req.block_id}' needs driver >= {need}, detected {have}",
            rule_id="block-requires-driver-min",
            field="requires.driver_min",
            fix_hint="Upgrade host driver or choose a compatible block version",
            confidence_context={"driver_version": field_conf.get("driver_version", "unknown")},
        )
    ]


def _handle_cuda_runtime(req: _Req, profile: Profile, _: dict[str, str]) -> list[CompatibilityIssue]:
    issues: list[CompatibilityIssue] = []
    profile_cuda = _profile_cuda(profile)
    if isinstance(req.value, dict):
        min_v = _to_float(req.value.get("min"))
        max_v = _to_float(req.value.get("max"))
        if profile_cuda is not None and min_v is not None and profile_cuda < min_v:
            issues.append(
                _requirement_issue(
                    req,
                    code="CUDA_RANGE_UNSUPPORTED",
                    message=f"Block '{req.block_id}' requires cuda >= {min_v}, profile has {profile_cuda}",
                    rule_id="block-requires-cuda-min",
                    field="requires.cuda_runtime.min",
                )
            )
        if profile_cuda is not None and max_v is not None and profile_cuda > max_v:
            issues.append(
                _requirement_issue(
                    req,
                    code="CUDA_RANGE_UNSUPPORTED",
                    message=f"Block '{req.block_id}' requires cuda <= {max_v}, profile has {profile_cuda}",
                    rule_id="block-requires-cuda-max",
                    field="requires.cuda_runtime.max",
                )
            )
    elif isinstance(req.value, list):
        allowed = {str(v) for v in req.value}
        actual = profile.cuda.variant if profile.cuda else ""
        if actual and actual not in allowed:
            issues.append(
                _requirement_issue(
                    req,
                    code="CUDA_VARIANT_UNSUPPORTED",
                    message=f"Block '{req.block_id}' requires one of {sorted(allowed)}, profile has '{actual}'",
                    rule_id="block-requires-cuda-variant",
                    field="requires.cuda_runtime",
                )
            )
    return issues


_REQUIREMENT_HANDLERS = {
    "arch": _handle_arch,
    "arch_id": _handle_arch,
    "os": _handle_os,
    "os_family_id": _handle_os_family,
    "os_version_id": _handle_os_version,
    "gpu_vendor": _handle_gpu_vendor,
    "gpu_vendor_id": _handle_gpu_vendor,
    "gpu_family_id": _handle_gpu_family,
    "container_runtime": _handle_runtime,
    "driver_min": _handle_driver_min,
    "cuda_runtime": _handle_cuda_runtime,
}


def evaluate_compatibility(
    profile: Profile,
    stack: StackSpec,
    *,
    blocks: list[BlockSpec] | None = None,
    strict_mode: bool = False,
    tuple_mode: str | None = None,
    tuple_catalog: TupleCatalog | None = None,
    rule_catalog: CompatibilityRuleCatalog | None = None,
) -> CompatibilityReport:
    """Evaluate compatibility and return structured diagnostics."""
    block_specs = blocks or []
    errors: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []
    info: list[CompatibilityIssue] = []
    trace: list[str] = []
    suggested_fixes: list[str] = []
    requirements: list[_Req] = []
    field_conf = profile.host_facts.confidence or {}
    layer_mode = tuple_mode or tuple_layer_mode()

    trace.append(f"profile={profile.id} schema={profile.schema_version}")
    trace.append(f"stack={stack.id} schema={stack.schema_version}")
    trace.append(f"blocks={','.join(stack.blocks) if stack.blocks else '<none>'}")
    trace.append(
        "derived_capabilities="
        + (",".join(profile.derived_capabilities) if profile.derived_capabilities else "<none>")
    )
    trace.append(f"tuple_layer_mode={layer_mode}")

    for b in block_specs:
        for k, v in (b.requires or {}).items():
            requirements.append(_Req(block_id=b.id, key=k, value=v))
        for other in b.incompatible_with:
            if other in stack.blocks:
                errors.append(
                    CompatibilityIssue(
                        code="BLOCK_CONFLICT",
                        severity="error",
                        message=f"Block '{b.id}' is incompatible with '{other}'",
                        rule_id="block-incompatible-with",
                        rule_version=1,
                        source=b.id,
                        field="incompatible_with",
                        fix_hint=f"Remove either '{b.id}' or '{other}' from stack blocks",
                    )
                )

    for req in requirements:
        handler = _REQUIREMENT_HANDLERS.get(req.key)
        if not handler:
            continue
        errors.extend(handler(req, profile, field_conf))
    tuple_decision = _evaluate_tuple_resolution(
        profile=profile,
        strict_mode=strict_mode,
        mode=layer_mode,
        tuple_catalog=tuple_catalog,
    )
    trace.extend(tuple_decision.get("trace", []))
    if tuple_decision.get("matched"):
        info.append(
            CompatibilityIssue(
                code="TUPLE_MATCHED",
                severity="info",
                message=f"Resolved tuple: {tuple_decision.get('tuple_id')}",
                source="tuple_catalog",
            )
        )
    else:
        mismatch_msg = tuple_decision.get("message") or "No supported tuple matched profile facts."
        mismatch_issue = CompatibilityIssue(
            code="TUPLE_UNSUPPORTED",
            severity="error" if layer_mode == "enforce" else "warning",
            message=mismatch_msg,
            source="tuple_catalog",
            field="profile",
            fix_hint="Adjust profile hardware facts or choose a tuple-supported profile/block combination.",
        )
        if layer_mode == "enforce":
            errors.append(mismatch_issue)
        elif layer_mode in {"warn", "shadow"}:
            warnings.append(mismatch_issue)
        suggested_fixes.extend(tuple_decision.get("suggested_fixes", []))

    catalog = rule_catalog or load_rule_catalog()
    for rule in catalog.rules:
        if not rule.enabled or rule.deprecated:
            continue
        _apply_catalog_rule(
            rule=rule,
            profile=profile,
            errors=errors,
            warnings=warnings,
            info=info,
            strict_mode=strict_mode,
            confidence=field_conf,
        )

    if not errors:
        info.append(
            CompatibilityIssue(
                code="COMPAT_OK",
                severity="info",
                message="Compatibility checks passed with current profile and stack selection.",
            )
        )
    else:
        suggested_fixes.append("Review block requirements and select compatible block/profile combinations.")

    effective_caps = list(dict.fromkeys(profile.derived_capabilities or []))
    summary = {
        "stack_blocks": stack.blocks,
        "block_requirements": [{r.key: r.value, "block_id": r.block_id} for r in requirements],
        "profile_restrictions": profile.constraints.model_dump(mode="json"),
        "effective_capabilities": effective_caps,
        "unknown_confidence_fields": sorted([k for k, v in field_conf.items() if v == "unknown"]),
    }
    report = CompatibilityReport(
        compatible=not errors,
        errors=errors,
        warnings=warnings,
        info=info,
        requirements_summary=summary,
        decision_trace=trace,
        suggested_fixes=suggested_fixes,
        tuple_decision=tuple_decision,
    )
    _log_diagnostics(report, profile.id, stack.id)
    return report


def _profile_cuda(profile: Profile) -> float | None:
    if profile.cuda is None:
        return None
    return _to_float(f"{profile.cuda.major}.{profile.cuda.minor}")


def _profile_tuple_facts(profile: Profile) -> dict[str, str]:
    gpu_vendor = (profile.gpu.vendor_id or profile.gpu.vendor or "").strip().lower()
    if not gpu_vendor:
        gpu_vendor = "cpu"
    return {
        "arch": profile.arch.value.lower(),
        "os_family_id": (profile.os_family_id or profile.os_family or profile.os or "").strip().lower(),
        "os_version_id": (profile.os_version_id or profile.os_version or "").strip().lower(),
        "container_runtime": profile.container_runtime.value.lower(),
        "gpu_vendor_id": gpu_vendor,
        "gpu_family_id": (profile.gpu.family_id or profile.gpu.family or "").strip().lower(),
    }


def _tuple_matches(profile: Profile, tup: SupportedTuple) -> tuple[bool, str]:
    facts = _profile_tuple_facts(profile)
    selector = tup.selector
    checks = (
        ("arch", selector.arch),
        ("os_family_id", selector.os_family_id),
        ("os_version_id", selector.os_version_id),
        ("container_runtime", selector.container_runtime),
        ("gpu_vendor_id", selector.gpu_vendor_id),
    )
    for key, expected in checks:
        actual = facts.get(key, "")
        if expected and actual and expected.lower() != actual.lower():
            return False, f"{key} expected '{expected}' got '{actual}'"
        if expected and not actual:
            return False, f"{key} expected '{expected}' got '<empty>'"
    if selector.gpu_family_id:
        actual_family = facts.get("gpu_family_id", "")
        if actual_family and selector.gpu_family_id.lower() != actual_family.lower():
            return False, f"gpu_family_id expected '{selector.gpu_family_id}' got '{actual_family}'"
    cuda_val = _profile_cuda(profile)
    if cuda_val is not None:
        if selector.cuda_min is not None and cuda_val < selector.cuda_min:
            return False, f"cuda_runtime expected >= {selector.cuda_min} got {cuda_val}"
        if selector.cuda_max is not None and cuda_val > selector.cuda_max:
            return False, f"cuda_runtime expected <= {selector.cuda_max} got {cuda_val}"
    driver_val = _to_float(profile.host_facts.driver_version)
    if selector.driver_min is not None and driver_val is not None and driver_val < selector.driver_min:
        return False, f"driver_version expected >= {selector.driver_min} got {driver_val}"
    return True, ""


def _evaluate_tuple_resolution(
    *,
    profile: Profile,
    strict_mode: bool,
    mode: str,
    tuple_catalog: TupleCatalog | None = None,
) -> dict[str, object]:
    if mode == "off":
        return {
            "enabled": False,
            "mode": mode,
            "matched": True,
            "tuple_id": "",
            "status": "disabled",
            "message": "Tuple layer disabled.",
            "trace": ["tuple_layer: disabled"],
            "suggested_fixes": [],
        }

    catalog = tuple_catalog or load_tuple_catalog()
    trace: list[str] = [f"tuple_layer: catalog_tuples={len(catalog.tuples)} mode={mode} strict={strict_mode}"]
    mismatches: list[str] = []
    first_experimental: SupportedTuple | None = None
    for tup in catalog.tuples:
        matched, reason = _tuple_matches(profile, tup)
        if matched:
            trace.append(f"tuple_layer: matched={tup.id} status={tup.status}")
            if tup.status == "supported":
                return {
                    "enabled": True,
                    "mode": mode,
                    "matched": True,
                    "tuple_id": tup.id,
                    "status": tup.status,
                    "message": f"Matched supported tuple '{tup.id}'.",
                    "base_image_hint": tup.base_image,
                    "wheelhouse_hint": tup.wheelhouse_path,
                    "trace": trace,
                    "suggested_fixes": [],
                }
            if first_experimental is None:
                first_experimental = tup
        else:
            mismatches.append(f"{tup.id}: {reason}")
    if first_experimental is not None:
        trace.append(f"tuple_layer: matched_experimental={first_experimental.id}")
        return {
            "enabled": True,
            "mode": mode,
            "matched": True,
            "tuple_id": first_experimental.id,
            "status": first_experimental.status,
            "message": f"Matched experimental tuple '{first_experimental.id}'.",
            "base_image_hint": first_experimental.base_image,
            "wheelhouse_hint": first_experimental.wheelhouse_path,
            "trace": trace,
            "suggested_fixes": ["Use a supported tuple for production workloads when available."],
        }
    trace.append("tuple_layer: no_match")
    return {
        "enabled": True,
        "mode": mode,
        "matched": False,
        "tuple_id": "",
        "status": "unsupported",
        "message": "No supported tuple matched current profile facts.",
        "mismatches": mismatches[:8],
        "trace": trace,
        "suggested_fixes": [
            "Update profile arch/runtime/GPU fields to align with supported tuples.",
            "Choose blocks with requirements compatible with your target profile tuple.",
        ],
    }


def _log_diagnostics(report: CompatibilityReport, profile_id: str, stack_id: str) -> None:
    counts: dict[str, int] = {}
    for issue in [*report.errors, *report.warnings, *report.info]:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    logger.info(
        "compatibility_evaluated profile=%s stack=%s compatible=%s counts=%s",
        profile_id,
        stack_id,
        report.compatible,
        counts,
    )


def _apply_catalog_rule(
    *,
    rule: CompatibilityRule,
    profile: Profile,
    errors: list[CompatibilityIssue],
    warnings: list[CompatibilityIssue],
    info: list[CompatibilityIssue],
    strict_mode: bool,
    confidence: dict[str, str],
) -> None:
    when = rule.when
    if when.arch and when.arch != profile.arch.value:
        return
    if when.os_family and (profile.os_family or profile.os).lower() != when.os_family.lower():
        return
    if when.gpu_vendor and (profile.gpu.vendor_id or profile.gpu.vendor or "").lower() != when.gpu_vendor.lower():
        return
    if when.gpu_family and (profile.gpu.family_id or profile.gpu.family or "").lower() != when.gpu_family.lower():
        return

    cc_val = _to_float(profile.gpu.compute_capability)
    if when.compute_capability_min is not None and cc_val is not None and cc_val < when.compute_capability_min:
        return
    if when.compute_capability_max is not None and cc_val is not None and cc_val > when.compute_capability_max:
        return

    outcome = rule.outcome
    req = rule.requires
    violated = False
    violated_field = ""
    if req.container_runtime is not None:
        if profile.container_runtime.value.lower() != req.container_runtime.lower():
            violated = True
            violated_field = "container_runtime"
    if not violated and req.driver_min is not None:
        drv = _to_float(profile.host_facts.driver_version)
        if drv is None:
            if rule.strict_hard and strict_mode and confidence.get("driver_version") == "detected":
                violated = True
                violated_field = "driver_version"
        elif drv < req.driver_min:
            violated = True
            violated_field = "driver_version"
    if not violated and (req.cuda_min is not None or req.cuda_max is not None):
        cuda_val = _to_float(f"{profile.cuda.major}.{profile.cuda.minor}") if profile.cuda else None
        if cuda_val is not None:
            if req.cuda_min is not None and cuda_val < req.cuda_min:
                violated = True
                violated_field = "cuda_runtime"
            if req.cuda_max is not None and cuda_val > req.cuda_max:
                violated = True
                violated_field = "cuda_runtime"

    if not violated and outcome.severity != "info":
        return

    issue = CompatibilityIssue(
        code=outcome.code,
        severity=outcome.severity,
        message=outcome.message,
        rule_id=rule.id,
        rule_version=rule.version,
        field=violated_field or None,
        fix_hint=outcome.fix_hint,
        confidence_context={k: v for k, v in confidence.items() if v != "detected"},
    )
    if outcome.severity == "error":
        if rule.strict_hard and strict_mode:
            errors.append(issue)
        else:
            warnings.append(issue.model_copy(update={"severity": "warning"}))
    elif outcome.severity == "warning":
        warnings.append(issue)
    else:
        info.append(issue)

