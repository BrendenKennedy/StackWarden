# Example Plans

## Diffusion on DGX Spark

```
$ stacksmith plan --profile dgx_spark --stack diffusion_fastapi

╭────────────────────────── Stacksmith Plan ───────────────────────────╮
│ Plan: plan_46d159906e84ea3c                                          │
╰──────────────────────────────────────────────────────────────────────╯
  Profile: dgx_spark
  Stack:   diffusion_fastapi
  Base:    nvcr.io/nvidia/pytorch:24.06-py3
  Builder: overlay
  Tag:     local/stacksmith:diffusion_fastapi-dgx_spark-cuda12.5-python_api-fastapi-46d159906e84
  FP:      46d159906e84ea3c0447f91a...

Steps (2):
  1. pull nvcr.io/nvidia/pytorch:24.06-py3
  2. build_overlay -> local/stacksmith:diffusion_fastapi-dgx_spark-cuda12.5-python_api-fastapi-46d159906e84
```

The resolver selected `nvcr.io/nvidia/pytorch:24.06-py3` as the base because:
- The stack's `base_role` is `pytorch`, which matches the candidate name
- DGX Spark profile gives this candidate a `score_bias` of 100
- No compatibility issues detected (all dependencies are ARM64-compatible)

## vLLM on DGX Spark

```
$ stacksmith plan --profile dgx_spark --stack llm_vllm

╭────────────────────────── Stacksmith Plan ───────────────────────────╮
│ Plan: plan_a1b2c3d4e5f6a7b8                                         │
╰──────────────────────────────────────────────────────────────────────╯
  Profile: dgx_spark
  Stack:   llm_vllm_fastapi
  Base:    nvcr.io/nvidia/pytorch:24.06-py3
  Builder: overlay
  Tag:     local/stacksmith:llm_vllm_fastapi-dgx_spark-cuda12.5-vllm-fastapi-a1b2c3d4e5f6
  FP:      a1b2c3d4e5f6a7b8...

Steps (2):
  1. pull nvcr.io/nvidia/pytorch:24.06-py3
  2. build_overlay -> local/stacksmith:llm_vllm_fastapi-dgx_spark-cuda12.5-vllm-fastapi-a1b2c3d4e5f6
```

## Mismatch Example: x86-only package on ARM64

If a stack includes `xformers` (which has limited ARM64 support):

```
$ stacksmith plan --profile dgx_spark --stack diffusion_with_xformers

  ...
  Warnings:
    - xformers has limited ARM64 support; torch SDPA will be used instead
```

The plan still generates (it's a warning, not an error), but the user is alerted to the potential issue.

## Incompatible Stack

If a profile disallows a serve type:

```
$ stacksmith plan --profile restricted_profile --stack triton_stack

Error: Stack is incompatible with profile:
  - serve type 'triton' is disallowed by profile 'restricted_profile'
```

The resolver raises an `IncompatibleStackError` and the plan is not generated.
