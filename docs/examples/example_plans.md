# Example Plans

Illustrative `stackwarden plan` outputs for common situations.

## DGX Spark + Diffusion

```bash
stackwarden plan --profile dgx_spark --stack diffusion_fastapi
```

Expected characteristics:

- resolved NVIDIA base image for the selected `base_role`
- `overlay` build strategy
- deterministic fingerprint and tag
- concise step list (pull + overlay build)

## DGX Spark + vLLM

```bash
stackwarden plan --profile dgx_spark --stack llm_vllm
```

Expected characteristics:

- DGX-certified stack warning behavior is explicit for non-DGX paths
- tuple/compatibility decision metadata appears when enabled
- deterministic output shape suitable for CI parsing (`--json`)

## Warning Path Example

```bash
stackwarden plan --profile dgx_spark --stack <stack_with_partial_arch_support>
```

Expected characteristics:

- plan can still succeed
- warnings clearly explain degraded/alternative execution assumptions

## Hard Incompatibility Example

```bash
stackwarden plan --profile restricted_profile --stack triton_stack
```

Expected characteristics:

- compatibility error returned before build
- explicit reason list (for example, profile-disallowed serve/runtime)
