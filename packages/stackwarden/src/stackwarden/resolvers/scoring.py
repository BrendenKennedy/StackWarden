"""Base candidate scoring and selection.

Scoring is deterministic: identical inputs always produce the same ordering.
Ties are broken by candidate name (ascending) to ensure stable results.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from stackwarden.resolvers.base_catalog import RuntimeBaseCandidate, candidates_for

if TYPE_CHECKING:
    from stackwarden.domain.models import Profile, ScoreBreakdown, StackSpec

_ROLE_MATCH_SCORE = 200
_CUDA_TAG_MATCH_SCORE = 50


def _word_boundary_match(needle: str, haystack: str) -> bool:
    """Match *needle* in *haystack* at word boundaries to prevent substring false positives."""
    return bool(re.search(rf"(?:^|[/\-_.])({re.escape(needle)})(?:$|[/\-_.])", haystack))


def _cuda_variant_match(variant: str, tag: str) -> bool:
    """Match CUDA variant in a tag at word boundaries (e.g. '12.1' must not match '12.10')."""
    return bool(re.search(rf"(?:^|[^0-9.])({re.escape(variant)})(?:$|[^0-9.])", tag))


def _pick_best_tag(candidate: RuntimeBaseCandidate, profile: Profile) -> tuple[str, int]:
    """Return ``(chosen_tag, cuda_score)`` preferring the CUDA-matching tag."""
    if not candidate.tags:
        return "latest", 0
    cuda_variant = profile.cuda.variant if profile.cuda else ""
    if cuda_variant:
        for tag in candidate.tags:
            if _cuda_variant_match(cuda_variant, tag):
                return tag, _CUDA_TAG_MATCH_SCORE
    return candidate.tags[0], 0


def score_candidate(candidate: RuntimeBaseCandidate, stack: StackSpec, profile: Profile) -> int:
    """Score a single base candidate against the stack + profile."""
    score = candidate.score_bias

    if _word_boundary_match(stack.components.base_role, candidate.name):
        score += _ROLE_MATCH_SCORE

    _, cuda_score = _pick_best_tag(candidate, profile)
    score += cuda_score

    return score


def score_candidate_detailed(
    candidate: RuntimeBaseCandidate, stack: StackSpec, profile: Profile
) -> ScoreBreakdown:
    """Score a candidate and return a full breakdown of each component."""
    from stackwarden.domain.models import ScoreBreakdown

    role_match = _ROLE_MATCH_SCORE if _word_boundary_match(stack.components.base_role, candidate.name) else 0
    chosen_tag, cuda_match = _pick_best_tag(candidate, profile)

    return ScoreBreakdown(
        candidate_name=candidate.name,
        candidate_tag=chosen_tag,
        score_bias=candidate.score_bias,
        role_match=role_match,
        cuda_match=cuda_match,
        total=candidate.score_bias + role_match + cuda_match,
    )


def select_base(
    profile: Profile, stack: StackSpec
) -> tuple[RuntimeBaseCandidate, str]:
    """Pick the highest-scoring base candidate and its best tag.

    Returns ``(candidate, chosen_tag)``.  Raises ``ValueError`` if the
    profile has no base candidates.
    """
    available = candidates_for(profile, stack)
    if not available:
        raise ValueError(f"No runtime base candidates available for profile '{profile.id}'")

    scored = [
        (score_candidate(c, stack, profile), c)
        for c in available
    ]
    scored.sort(key=lambda pair: (-pair[0], pair[1].name))

    best = scored[0][1]
    chosen_tag, _ = _pick_best_tag(best, profile)
    return best, chosen_tag


def select_base_detailed(
    profile: Profile, stack: StackSpec
) -> tuple[RuntimeBaseCandidate, str, list[ScoreBreakdown], str]:
    """Pick the best candidate and return full scoring details.

    Returns ``(candidate, chosen_tag, all_breakdowns, selected_reason)``.
    """
    available = candidates_for(profile, stack)
    if not available:
        raise ValueError(f"No runtime base candidates available for profile '{profile.id}'")

    breakdowns = [
        score_candidate_detailed(c, stack, profile)
        for c in available
    ]
    breakdowns.sort(key=lambda b: (-b.total, b.candidate_name))

    best_bd = breakdowns[0]
    best = next(
        (c for c in available if c.name == best_bd.candidate_name),
        None,
    )
    if best is None:
        raise ValueError(f"Candidate '{best_bd.candidate_name}' not found in profile")
    chosen_tag, _ = _pick_best_tag(best, profile)

    parts = []
    if best_bd.role_match:
        parts.append(f"{stack.components.base_role} role match (+{best_bd.role_match})")
    if best_bd.cuda_match:
        parts.append(f"CUDA tag match (+{best_bd.cuda_match})")
    if best_bd.score_bias:
        parts.append(f"score_bias (+{best_bd.score_bias})")
    reason = f"Highest score ({best_bd.total}): " + ", ".join(parts) if parts else f"Default selection (score={best_bd.total})"

    return best, chosen_tag, breakdowns, reason
