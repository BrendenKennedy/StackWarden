from __future__ import annotations

from typer.testing import CliRunner

from stackwarden.cli import app
from stackwarden.ui.create_wizard_engine import CreateWizardResult


def test_profiles_wizard_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.run_profile_create_wizard",
        lambda **_: CreateWizardResult(entity="profile", id="p1", valid=True, yaml="id: p1\n"),
    )
    out = runner.invoke(app, ["profiles", "wizard", "--non-interactive", "--dry-run", "--json"])
    assert out.exit_code == 0, out.output
    assert '"entity": "profile"' in out.output
    assert '"id": "p1"' in out.output


def test_blocks_wizard_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.run_block_create_wizard",
        lambda **_: CreateWizardResult(entity="block", id="b1", valid=True, yaml="id: b1\n"),
    )
    out = runner.invoke(app, ["blocks", "wizard", "--preset", "vllm", "--non-interactive", "--dry-run", "--json"])
    assert out.exit_code == 0, out.output
    assert '"entity": "block"' in out.output
    assert '"id": "b1"' in out.output


def test_stacks_wizard_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.run_stack_create_wizard",
        lambda **_: CreateWizardResult(entity="stack", id="s1", valid=True, yaml="id: s1\n"),
    )
    out = runner.invoke(app, ["stacks", "wizard", "--non-interactive", "--dry-run", "--json"])
    assert out.exit_code == 0, out.output
    assert '"entity": "stack"' in out.output
    assert '"id": "s1"' in out.output
