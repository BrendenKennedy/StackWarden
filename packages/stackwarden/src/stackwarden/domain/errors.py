"""Custom exception hierarchy for StackWarden.

Exit codes:
    1  — generic / unclassified error
    2  — drift detected (verify mismatch)
    3  — immutable violation (DriftError)
    4  — registry policy violation
    5  — build failure
    6  — hook failure
"""

# Deterministic exit codes
EXIT_GENERIC = 1
EXIT_DRIFT = 2
EXIT_IMMUTABLE = 3
EXIT_REGISTRY_POLICY = 4
EXIT_BUILD_FAILURE = 5
EXIT_HOOK_FAILURE = 6
EXIT_CANCELED = 7


class StackWardenError(Exception):
    """Base exception for all StackWarden errors."""

    exit_code: int = EXIT_GENERIC


class ProfileNotFoundError(StackWardenError):
    """Raised when a requested hardware profile cannot be located."""

    def __init__(self, profile_id: str) -> None:
        self.profile_id = profile_id
        super().__init__(f"Profile not found: {profile_id}")


class StackNotFoundError(StackWardenError):
    """Raised when a requested stack spec cannot be located."""

    def __init__(self, stack_id: str) -> None:
        self.stack_id = stack_id
        super().__init__(f"Stack not found: {stack_id}")


class BlockNotFoundError(StackWardenError):
    """Raised when a requested block spec cannot be located."""

    def __init__(self, block_id: str) -> None:
        self.block_id = block_id
        super().__init__(f"Block not found: {block_id}")


class IncompatibleStackError(StackWardenError):
    """Raised when a stack is incompatible with the target profile."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__(
            "Stack is incompatible with profile:\n" + "\n".join(f"  - {i}" for i in issues)
        )


class SchemaValidationError(StackWardenError):
    """Raised when schema or cross-field validation fails."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"Validation error on '{field}': {message}")


# Keep backward-compatible alias
ValidationError = SchemaValidationError


class BuildError(StackWardenError):
    """Raised when a container build or pull operation fails."""

    exit_code = EXIT_BUILD_FAILURE

    def __init__(self, step: str, detail: str) -> None:
        self.step = step
        super().__init__(f"Build failed at step '{step}': {detail}")


class DriftError(StackWardenError):
    """Raised when --immutable is set and drift is detected."""

    exit_code = EXIT_IMMUTABLE

    def __init__(self, tag: str, detail: str) -> None:
        self.tag = tag
        super().__init__(
            f"Immutable mode: drift detected on '{tag}': {detail}"
        )


class RegistryPolicyError(StackWardenError):
    """Raised when a base image violates registry allow/deny policy."""

    exit_code = EXIT_REGISTRY_POLICY


class HookFailureError(StackWardenError):
    """Raised when post-build hooks fail."""

    exit_code = EXIT_HOOK_FAILURE


class CatalogError(StackWardenError):
    """Raised on catalog persistence failures."""


class CancellationRequestedError(StackWardenError):
    """Raised when a cooperative cancellation request is honored."""

    exit_code = EXIT_CANCELED
