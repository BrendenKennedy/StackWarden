# StackWarden Catalog

Profiles, stacks, blocks, and rules for hardware-aware ML container builds.

## ARM64 / Native Arm Support

We aim to get everything running on native ARM (e.g. DGX Spark, Graviton, Apple Silicon). Most stacks build and run on ARM64 without issue. A few are unportable due to upstream constraints:

| Stack | Issue | Workaround |
|-------|-------|------------|
| `robotics_isaac_lab` | Isaac Sim (underlying simulator) is x86-64 only; no ARM64 wheels or source path | Use x86-64 hardware |
| `llm_finetune_nemo` | NeMo pulls `opencc` (no aarch64 wheels); build-from-source fails in NGC env | Use `llm_finetune_torchtune` on ARM, or run NeMo on x86-64 |

If you hit other ARM64 build failures, check `generated/stress_test_report.md` for the latest compatibility notes.
