"""Variant parsing, validation, and normalization.

Extracted from ``cli.py`` so that both the CLI and wizard can share the
same logic without coupling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stackwarden.domain.models import StackSpec


def parse_variants(var_list: list[str] | None) -> dict[str, bool | str]:
    """Parse ``key=value`` strings into a typed variant dict.

    Bool-like values (``true``/``false``, case-insensitive) are coerced to
    native ``bool``; everything else stays as ``str``.
    """
    if not var_list:
        return {}
    variants: dict[str, bool | str] = {}
    for item in var_list:
        if "=" not in item:
            raise ValueError(f"Variant must be key=value, got: {item}")
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if v.lower() == "true":
            variants[k] = True
        elif v.lower() == "false":
            variants[k] = False
        else:
            variants[k] = v
    return variants


def validate_variant_flags(
    stack: StackSpec, variants: dict[str, bool | str],
) -> None:
    """Raise ``ValueError`` if any variant key is not defined by *stack*."""
    defined = stack.variants
    for key in variants:
        if key not in defined:
            raise ValueError(
                f"Unknown variant '{key}' for stack '{stack.id}'. "
                f"Valid variants: {', '.join(defined) or '(none)'}"
            )


def normalize_variants(
    stack: StackSpec, raw: dict[str, bool | str],
) -> dict[str, bool | str]:
    """Fill defaults, validate types, and sort keys.

    Returns a new dict with every variant defined by *stack* present (using
    the default when the caller did not supply one).  Unknown keys are
    rejected and type mismatches raise ``ValueError``.
    """
    defined = stack.variants
    validate_variant_flags(stack, raw)

    result: dict[str, bool | str] = {}
    for name, vdef in sorted(defined.items()):
        if name in raw:
            value = raw[name]
        else:
            value = vdef.default

        if vdef.type == "bool":
            if isinstance(value, str):
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                else:
                    raise ValueError(
                        f"Variant '{name}' is bool but got non-boolean string: {value!r}"
                    )
            if not isinstance(value, bool):
                raise ValueError(
                    f"Variant '{name}' is bool but got {type(value).__name__}: {value!r}"
                )
        elif vdef.type == "enum":
            value = str(value)
            if value not in vdef.options:
                raise ValueError(
                    f"Variant '{name}' must be one of {vdef.options}, got: {value!r}"
                )
        result[name] = value

    return result
