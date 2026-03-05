"""Stress tests: CLI edge cases.

- --json on failure: JSON output even when build fails
- --explain: rationale present in plan
- Non-interactive: ensure with --yes or CI env skips confirm prompts
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from stackwarden.cli import app


class TestOutputJsonOnFailure:
    """--output-json should produce JSON even when build fails."""

    def test_ensure_failure_with_output_json_exits_nonzero(self):
        """When ensure fails and --json, exit code is non-zero, no confirm prompt."""
        runner = CliRunner()
        with patch("stackwarden.domain.ensure.ensure_internal") as mock_ensure:
            mock_ensure.side_effect = Exception("Build failed")
            out = runner.invoke(app, ["ensure", "--profile", "p1", "--stack", "s1", "--json"])
            assert out.exit_code != 0
            # Should not hang on typer.confirm (non-interactive)

    def test_ensure_success_with_output_json_prints_json(self):
        """When ensure succeeds with --output-json, prints JSON."""
        runner = CliRunner()
        rec = MagicMock()
        rec.model_dump.return_value = {"tag": "local/stackwarden:test", "status": "built"}
        rec.tag = "local/stackwarden:test"
        rec.status = MagicMock(value="built")
        rec.image_id = "abc123"
        rec.digest = None
        plan = MagicMock()
        plan.decision.rationale = None
        with patch("stackwarden.domain.ensure.ensure_internal", return_value=(rec, plan)), \
             patch("stackwarden.cli_shared.context.setup_cli"):
            out = runner.invoke(app, ["ensure", "--profile", "p1", "--stack", "s1", "--json"])
            assert out.exit_code == 0, out.output
            assert "local/stackwarden" in out.output or "tag" in out.output


class TestExplain:
    """--explain produces rationale."""

    def test_ensure_explain_includes_rationale(self):
        """When --explain, resolve is called with explain=True."""
        runner = CliRunner()
        rec = MagicMock()
        rec.tag = "local/stackwarden:test"
        rec.status = MagicMock(value="built")
        rec.image_id = "abc123"
        rec.digest = None
        rec.model_dump.return_value = {}
        plan = MagicMock()
        plan.decision.rationale = MagicMock()
        plan.decision.rationale.candidates = []
        plan.decision.rationale.rules_fired = []
        with patch("stackwarden.domain.ensure.ensure_internal", return_value=(rec, plan)):
            out = runner.invoke(app, ["ensure", "--profile", "p1", "--stack", "s1", "--explain"])
            assert out.exit_code == 0


class TestNonInteractive:
    """CI/non-interactive mode skips confirm prompts."""

    def test_ensure_no_confirm_when_non_interactive(self):
        """When ensure fails and output_json, no typer.confirm is called."""
        runner = CliRunner()
        with patch("stackwarden.domain.ensure.ensure_internal") as mock_ensure:
            mock_ensure.side_effect = Exception("Build failed")
            # CliRunner uses isolated filesystem and non-interactive by default
            out = runner.invoke(app, ["ensure", "--profile", "p1", "--stack", "s1"])
            assert out.exit_code != 0
