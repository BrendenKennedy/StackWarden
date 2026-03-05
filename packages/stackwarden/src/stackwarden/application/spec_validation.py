"""Application-facing validation adapter for spec create/update flows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stackwarden.web.util.validation import (  # noqa: F401
    ConflictError,
    ValidationErrors,
    run_block_security_validation,
    run_profile_security_validation,
    run_stack_security_validation,
    validate_id_available_file,
    validate_id_available_loader,
    validate_spec_id,
)

__all__ = [
    "ConflictError",
    "ValidationErrors",
    "run_block_security_validation",
    "run_profile_security_validation",
    "run_stack_security_validation",
    "validate_id_available_file",
    "validate_id_available_loader",
    "validate_spec_id",
]


def ensure_id_available(spec_id: str, spec_dir: Path, loader: Any) -> None:
    """Compatibility wrapper to keep id-availability check semantics centralized."""
    validate_id_available_file(spec_id, spec_dir)
    validate_id_available_loader(spec_id, loader)
