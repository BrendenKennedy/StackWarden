"""Plan resolver — PURE FUNCTION.

``resolve()`` accepts fully-loaded domain objects and returns a ``Plan``.
It must **never** touch Docker, the filesystem, or the catalog.
All inputs are passed explicitly; there is no hidden state.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from stacksmith import __version__ as _builder_version
from stacksmith.domain.enums import BuildStrategy
from stacksmith.domain.errors import IncompatibleStackError
from stacksmith.domain.hashing import fingerprint, generate_tag
from stacksmith.domain.models import (
    BlockSpec,
    DecisionRationale,
    Plan,
    PlanArtifact,
    PlanDecision,
    PlanStep,
    Profile,
    StackSpec,
)
from stacksmith.resolvers.compatibility import evaluate_compatibility
from stacksmith.domain.tuple_catalog import TupleCatalog
from stacksmith.resolvers.rule_catalog import CompatibilityRuleCatalog
from stacksmith.resolvers.build_optimization import compute_build_optimization
from stacksmith.resolvers.rules import evaluate_all
from stacksmith.resolvers.scoring import select_base, select_base_detailed
from stacksmith.resolvers.validators import validate_profile, validate_stack


def resolve(
    profile: Profile,
    stack: StackSpec,
    *,
    blocks: list[BlockSpec] | None = None,
    base_digest: str | None = None,
    template_hash: str | None = None,
    variants: dict[str, str] | None = None,
    explain: bool = False,
    strict_mode: bool = False,
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
        blocks=blocks,
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
    if explain:
        candidate, chosen_tag, breakdowns, selected_reason = select_base_detailed(profile, stack)
        rationale = _build_rationale(
            profile, stack, breakdowns, selected_reason, warnings, errors,
            variants, base_digest, compat_report=compat.model_dump(mode="json"),
        )
    else:
        candidate, chosen_tag = select_base(profile, stack)
    base_image = f"{candidate.name}:{chosen_tag}"

    # 5. Compute fingerprint + tag
    fp = fingerprint(
        profile, stack, base_image, base_digest, template_hash,
        variants=variants,
    )
    tag = generate_tag(stack, profile, fp)

    # 6. Build metadata labels
    labels = {
        "stacksmith.profile": profile.id,
        "stacksmith.stack": stack.id,
        "stacksmith.fingerprint": fp,
        "stacksmith.base_digest": base_digest or "",
        "stacksmith.schema_version": str(stack.schema_version),
        "stacksmith.profile_schema_version": str(profile.schema_version),
        "stacksmith.block_schema_version": str(max((b.schema_version for b in (blocks or [])), default=1)),
        "stacksmith.template_hash": template_hash or "",
        "stacksmith.build_strategy": stack.build_strategy.value,
        "stacksmith.pip_install_mode": stack.components.pip_install_mode,
        "stacksmith.pip_wheelhouse_path": stack.components.pip_wheelhouse_path,
        "stacksmith.tuple_id": str(compat.tuple_decision.get("tuple_id", "")),
        "stacksmith.tuple_status": str(compat.tuple_decision.get("status", "")),
        "stacksmith.tuple_mode": str(compat.tuple_decision.get("mode", "")),
        "stacksmith.builder_version": _builder_version,
        "stacksmith.created_at": datetime.now(timezone.utc).isoformat(),
    }
    if variants:
        labels["stacksmith.variants"] = json.dumps(
            dict(sorted(variants.items())), separators=(",", ":")
        )

    # 7. Build steps
    optimization = compute_build_optimization(profile, stack)
    warnings.extend(optimization.warnings)
    build_args = {"PYTHON_VERSION": profile.defaults.python}
    build_args.update(optimization.build_args)
    if variants:
        for k, v in variants.items():
            build_args[f"VARIANT_{k.upper()}"] = str(v)

    labels["stacksmith.build_optimization"] = json.dumps(
        {
            "strategy": optimization.strategy,
            "cpu_parallelism": optimization.cpu_parallelism,
            "memory_budget_gb": optimization.memory_budget_gb,
            "oom_risk": optimization.oom_risk,
        },
        separators=(",", ":"),
    )

    steps = _build_steps(
        stack,
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
    from stacksmith.resolvers.rules import (
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
