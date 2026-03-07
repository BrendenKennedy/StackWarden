"""Single source for shared create contract constants."""

SPEC_ID_PATTERN = r"^[a-z][a-z0-9_\-]{2,63}$"
ALLOWED_BUILD_STRATEGIES = ("pull", "overlay")
DEFAULT_PROFILE_CREATE_SCHEMA_VERSION = 3
DEFAULT_STACK_CREATE_SCHEMA_VERSION = 3
DEFAULT_LAYER_CREATE_SCHEMA_VERSION = 2
STACK_LAYER_IDS = (
    "inference_engine_layer",
    "optimization_compilation_layer",
    "core_compute_layer",
    "driver_accelerator_layer",
    "system_runtime_layer",
    "application_orchestration_layer",
    "observability_operations_layer",
    "serving_layer",
)
