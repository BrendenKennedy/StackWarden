"""Shared render helpers for CLI flows."""

from __future__ import annotations


def print_rationale(console, rationale) -> None:
    """Render a DecisionRationale to the console."""
    console.print("\n[bold]Decision Rationale:[/bold]")
    console.print(f"  Base digest: {rationale.base_digest_status}")

    if rationale.rules_fired:
        console.print("\n  [bold]Rules evaluated:[/bold]")
        for rule in rationale.rules_fired:
            outcome = rule.get("outcome", "")
            color = {"pass": "green", "warn": "yellow", "fail": "red"}.get(outcome, "")
            styled = f"[{color}]{outcome}[/{color}]" if color else outcome
            detail = f" - {rule['detail']}" if rule.get("detail") else ""
            console.print(f"    {rule['rule']}: {styled}{detail}")

    if rationale.candidates:
        console.print("\n  [bold]Candidate scores:[/bold]")
        for bd in rationale.candidates:
            parts = []
            if bd.score_bias:
                parts.append(f"bias={bd.score_bias}")
            if bd.role_match:
                parts.append(f"role=+{bd.role_match}")
            if bd.cuda_match:
                parts.append(f"cuda=+{bd.cuda_match}")
            breakdown = ", ".join(parts) if parts else "no bonuses"
            console.print(f"    {bd.candidate_name}:{bd.candidate_tag}  total={bd.total} ({breakdown})")

    if rationale.selected_reason:
        console.print(f"\n  [bold]Selected:[/bold] {rationale.selected_reason}")

    if rationale.variant_effects:
        console.print("\n  [bold]Variant effects:[/bold]")
        for eff in rationale.variant_effects:
            console.print(f"    - {eff}")
