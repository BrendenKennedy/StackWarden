"""Tests for wizard command generation."""

from __future__ import annotations

from stacksmith.ui.wizard import WizardFlags, WizardSelection, build_command


class TestBuildCommand:
    def test_minimal(self):
        sel = WizardSelection(
            profile_id="x86_cuda",
            stack_id="llm_vllm",
        )
        cmd = build_command(sel)
        assert cmd == "stacksmith ensure --profile x86_cuda --stack llm_vllm"

    def test_with_variants_sorted(self):
        sel = WizardSelection(
            profile_id="dgx_spark",
            stack_id="diffusion_fastapi",
            variants={"zeta": "z", "alpha": "a"},
        )
        cmd = build_command(sel)
        assert "--var alpha=a" in cmd
        assert "--var zeta=z" in cmd
        assert cmd.index("alpha") < cmd.index("zeta")

    def test_bool_variant_lowercase(self):
        sel = WizardSelection(
            profile_id="x86_cuda",
            stack_id="test",
            variants={"xformers": True, "debug": False},
        )
        cmd = build_command(sel)
        assert "--var debug=false" in cmd
        assert "--var xformers=true" in cmd

    def test_all_flags(self):
        sel = WizardSelection(
            profile_id="x86_cuda",
            stack_id="test",
            flags=WizardFlags(
                rebuild=True,
                upgrade_base=True,
                immutable=True,
                no_hooks=True,
                explain=True,
            ),
        )
        cmd = build_command(sel)
        assert "--rebuild" in cmd
        assert "--upgrade-base" in cmd
        assert "--immutable" in cmd
        assert "--no-hooks" in cmd
        assert "--explain" in cmd

    def test_no_flags_when_false(self):
        sel = WizardSelection(
            profile_id="x86_cuda",
            stack_id="test",
            flags=WizardFlags(),
        )
        cmd = build_command(sel)
        assert "--rebuild" not in cmd
        assert "--upgrade-base" not in cmd
        assert "--immutable" not in cmd
        assert "--no-hooks" not in cmd
        assert "--explain" not in cmd

    def test_deterministic(self):
        sel = WizardSelection(
            profile_id="dgx_spark",
            stack_id="diffusion_fastapi",
            variants={"b": "2", "a": "1"},
            flags=WizardFlags(immutable=True),
        )
        cmd1 = build_command(sel)
        cmd2 = build_command(sel)
        assert cmd1 == cmd2

    def test_starts_with_stacksmith_ensure(self):
        sel = WizardSelection(
            profile_id="p", stack_id="s",
        )
        assert build_command(sel).startswith("stacksmith ensure")
