"""Plan resolver — PURE FUNCTION.

``resolve()`` accepts fully-loaded domain objects and returns a ``Plan``.
It must **never** touch Docker, the filesystem, or the catalog.
All inputs are passed explicitly; there is no hidden state.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from stackwarden import __version__ as _builder_version
from stackwarden.domain.enums import BuildStrategy
from stackwarden.domain.errors import IncompatibleStackError
from stackwarden.domain.hashing import fingerprint, generate_tag
from stackwarden.domain.models import (
    LayerSpec,
    DecisionRationale,
    Plan,
    PlanArtifact,
    PlanDecision,
    PlanStep,
    Profile,
    StackSpec,
)
from stackwarden.resolvers.compatibility import evaluate_compatibility
from stackwarden.domain.tuple_catalog import TupleCatalog
from stackwarden.resolvers.rule_catalog import CompatibilityRuleCatalog
from stackwarden.resolvers.build_optimization import compute_build_optimization
from stackwarden.resolvers.rules import evaluate_all
from stackwarden.resolvers.scoring import select_base, select_base_detailed
from stackwarden.resolvers.validators import validate_profile, validate_stack


def _split_image_ref(image_ref: str) -> tuple[str, str | None]:
    value = image_ref.strip()
    if not value:
        return "", None
    if ":" in value:
        name, tag = value.rsplit(":", 1)
        if "/" in tag:
            return value, None
        return name, tag
    return value, None


def _stack_with_tuple_hints(stack: StackSpec, tuple_decision: dict[str, object]) -> StackSpec:
    base_hint = str(tuple_decision.get("base_image_hint") or "").strip()
    wheelhouse_hint = str(tuple_decision.get("wheelhouse_hint") or "").strip()
    if not base_hint and not wheelhouse_hint:
        return stack

    overrides = dict(stack.policy_overrides or {})
    if base_hint:
        base_image, base_tag = _split_image_ref(base_hint)
        if base_image:
            overrides["base_image"] = base_image
        if base_tag:
            overrides["base_tag"] = base_tag
    if wheelhouse_hint:
        overrides["pip_wheelhouse_path_hint"] = wheelhouse_hint
    return stack.model_copy(update={"policy_overrides": overrides})


def resolve(
    profile: Profile,
    stack: StackSpec,
    *,
    layers: list[LayerSpec] | None = None,
    base_digest: str | None = None,
    template_hash: str | None = None,
    variants: dict[str, str] | None = None,
    explain: bool = False,
    strict_mode: bool = False,
    strict_host_optimization: bool = False,
    tuple_mode: str | None = None,
    tuple_catalog: TupleCatalog | None = None,
    rule_catalog: CompatibilityRuleCatalog | None = None,
) -> Plan:
    """Resolve a profile + stack into an executable Plan.

    Parameters
    ----------
    profile:
        Hardware profile (already loaded/validated by caller).
    stack:
        Stack specification (already loaded/validated by caller).
    base_digest:
        Optional SHA-256 digest of the selected base image.  If provided the
        fingerprint becomes fully reproducible; otherwise a placeholder is used.
    template_hash:
        Optional hash of the Dockerfile template.  Included in the fingerprint
        so template changes trigger rebuilds.
    variants:
        Optional variant overrides (key=value).  Included in the fingerprint
        and injected as build_args and labels.
    explain:
        When True, attach a ``DecisionRationale`` with full scoring
        breakdown and rule evaluation details.
    """
    # 1. Validate schemas
    validate_profile(profile)
    validate_stack(stack)

    # 2. Compatibility rules
    compat = evaluate_compatibility(
        profile,
        stack,
        layers=layers,
        strict_mode=strict_mode,
        tuple_mode=tuple_mode,
        tuple_catalog=tuple_catalog,
        rule_catalog=rule_catalog,
    )
    warnings, errors = evaluate_all(profile, stack)
    warnings.extend([w.message for w in compat.warnings])
    warnings.extend([i.message for i in compat.info])
    errors.extend([e.message for e in compat.errors])
    if errors:
        rendered = [
            f"{e.code}: {e.message}" for e in compat.errors
        ] or errors
        raise IncompatibleStackError(rendered)

    # 3. Mutable tag warning
    if not base_digest:
        warnings.append(
            "Base tag is mutable; build may not be reproducible. "
            "Consider pinning a digest."
        )

    # 4. Select base candidate
    rationale: DecisionRationale | None = None
    effective_stack = _stack_with_tuple_hints(stack, compat.tuple_decision)
    if explain:
        candidate, chosen_tag, breakdowns, selected_reason = select_base_detailed(profile, effective_stack)
        rationale = _build_rationale(
            profile, effective_stack, breakdowns, selected_reason, warnings, errors,
            variants, base_digest, compat_report=compat.model_dump(mode="json"),
        )
    else:
        candidate, chosen_tag = select_base(profile, effective_stack)
    base_image = f"{candidate.name}:{chosen_tag}"

    # 5. Compute fingerprint + tag
    fp = fingerprint(
        profile, effective_stack, base_image, base_digest, template_hash,
        variants=variants,
    )
    tag = generate_tag(effective_stack, profile, fp)

    # 6. Build metadata labels
    labels = {
        "stackwarden.profile": profile.id,
        "stackwarden.stack": effective_stack.id,
        "stackwarden.fingerprint": fp,
        "stackwarden.base_digest": base_digest or "",
        "stackwarden.schema_version": str(effective_stack.schema_version),
        "stackwarden.profile_schema_version": str(profile.schema_version),
        "stackwarden.layer_schema_version": str(max((layer.schema_version for layer in (layers or [])), default=1)),
        # Legacy compatibility label kept during Blocks->Layers migration.
        "stackwarden.block_schema_version": str(max((layer.schema_version for layer in (layers or [])), default=1)),
        "stackwarden.template_hash": template_hash or "",
        "stackwarden.build_strategy": effective_stack.build_strategy.value,
        "stackwarden.pip_install_mode": effective_stack.components.pip_install_mode,
        "stackwarden.pip_wheelhouse_path": effective_stack.components.pip_wheelhouse_path,
        "stackwarden.tuple_id": str(compat.tuple_decision.get("tuple_id", "")),
        "stackwarden.tuple_status": str(compat.tuple_decision.get("status", "")),
        "stackwarden.tuple_mode": str(compat.tuple_decision.get("mode", "")),
        "stackwarden.tuple_base_image_hint": str(compat.tuple_decision.get("base_image_hint", "")),
        "stackwarden.tuple_wheelhouse_hint": str(compat.tuple_decision.get("wheelhouse_hint", "")),
        "stackwarden.builder_version": _builder_version,
        "stackwarden.created_at": datetime.now(timezone.utc).isoformat(),
    }
    if variants:
        labels["stackwarden.variants"] = json.dumps(
            dict(sorted(variants.items())), separators=(",", ":")
        )

    # 7. Build steps
    try:
        optimization = compute_build_optimization(
            profile,
            effective_stack,
            layers=layers,
            strict_host_specific=strict_host_optimization,
        )
    except ValueError as exc:
        raise IncompatibleStackError([str(exc)]) from exc
    warnings.extend(optimization.warnings)
    build_args = {"PYTHON_VERSION": profile.defaults.python}
    build_args.update(optimization.build_args)
    wheelhouse_hint = str(compat.tuple_decision.get("wheelhouse_hint") or "").strip()
    if wheelhouse_hint:
        build_args["STACKWARDEN_PIP_WHEELHOUSE_PATH_HINT"] = wheelhouse_hint
        labels["stackwarden.pip_wheelhouse_path_hint"] = wheelhouse_hint
    if variants:
        for k, v in variants.items():
            build_args[f"VARIANT_{k.upper()}"] = str(v)

    labels["stackwarden.build_optimization"] = json.dumps(
        {
            "strategy": optimization.strategy,
            "cpu_parallelism": optimization.cpu_parallelism,
            "memory_budget_gb": optimization.memory_budget_gb,
            "oom_risk": optimization.oom_risk,
        },
        separators=(",", ":"),
    )
    labels["stackwarden.host_optimization"] = json.dumps(
        {
            "policy": optimization.policy,
            "strict_host_specific": optimization.strict_host_specific,
            "host_signature": optimization.host_signature,
            "gpu_family": optimization.gpu_family,
            "gpu_compute_capability": optimization.gpu_compute_capability,
            "driver_version": optimization.driver_version,
            "torch_dtype": optimization.torch_dtype,
            "attention_backend": optimization.attention_backend,
            "torch_compile_enabled": optimization.torch_compile_enabled,
            "tf32_enabled": optimization.tf32_enabled,
        },
        separators=(",", ":"),
    )

    steps = _build_steps(
        effective_stack,
        base_image,
        tag,
        labels,
        profile,
        build_args,
        optimization.buildx_flags,
    )

    # 8. Assemble
    decision = PlanDecision(
        base_image=base_image,
        base_digest=base_digest,
        builder=stack.build_strategy.value,
        warnings=warnings,
        rationale=rationale,
        tuple_decision=compat.tuple_decision,
        build_optimization=optimization,
    )

    artifact = PlanArtifact(
        tag=tag,
        fingerprint=fp,
        labels=labels,
    )

    return Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:16]}",
        profile_id=profile.id,
        stack_id=stack.id,
        decision=decision,
        steps=steps,
        artifact=artifact,
    )


def _build_steps(
    stack: StackSpec,
    base_image: str,
    tag: str,
    labels: dict[str, str],
    profile: Profile,
    build_args: dict[str, str],
    buildx_flags: list[str] | None = None,
) -> list[PlanStep]:
    """Generate the ordered list of execution steps."""
    steps: list[PlanStep] = []

    steps.append(PlanStep(type="pull", image=base_image))

    if stack.build_strategy == BuildStrategy.OVERLAY:
        steps.append(
            PlanStep(
                type="build_overlay",
                dockerfile_template="specs/templates/Dockerfile.overlay.j2",
                context_dir=".",
                build_args=build_args,
                buildx_flags=buildx_flags or [],
                tags=[tag],
                labels=labels,
            )
        )
    elif stack.build_strategy == BuildStrategy.PULL:
        steps.append(
            PlanStep(
                type="tag",
                image=base_image,
                tags=[tag],
                labels=labels,
            )
        )
    else:
        raise ValueError(f"Unknown build strategy: {stack.build_strategy!r}")

    return steps


def _build_rationale(
    profile: Profile,
    stack: StackSpec,
    breakdowns: list,
    selected_reason: str,
    warnings: list[str],
    errors: list[str],
    variants: dict[str, str] | None,
    base_digest: str | None,
    compat_report: dict | None = None,
) -> DecisionRationale:
    """Assemble a ``DecisionRationale`` from rule + scoring results."""
    from stackwarden.resolvers.rules import (
        check_arch_compatibility,
        check_required_capabilities,
        check_serve_disallowed,
    )

    rules_fired: list[dict[str, str]] = []
    for rule_fn in [check_arch_compatibility, check_serve_disallowed, check_required_capabilities]:
        issues = rule_fn(profile, stack)
        if issues:
            for issue in issues:
                outcome = "fail" if issue.startswith("ERROR:") else "warn"
                rules_fired.append({
                    "rule": rule_fn.__name__,
                    "outcome": outcome,
                    "detail": issue.removeprefix("ERROR: "),
                })
        else:
            rules_fired.append({
                "rule": rule_fn.__name__,
                "outcome": "pass",
                "detail": "",
            })

    variant_effects: list[str] = []
    if variants:
        for k, v in sorted(variants.items()):
            variant_effects.append(f"VARIANT_{k.upper()}={v} added as build arg")

    return DecisionRationale(
        rules_fired=rules_fired,
        candidates=breakdowns,
        selected_reason=selected_reason,
        variant_effects=variant_effects,
        base_digest_status="known" if base_digest else "unknown_until_pull",
        compatibility_report=compat_report or {},
    )
