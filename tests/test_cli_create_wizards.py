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


def test_layers_wizard_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(
        "stackwarden.ui.wizard_entities.run_layer_create_wizard",
        lambda **_: CreateWizardResult(entity="layer", id="l1", valid=True, yaml="id: l1\n"),
    )
    out = runner.invoke(app, ["layers", "wizard", "--preset", "vllm_model_runtime", "--non-interactive", "--dry-run", "--json"])
    assert out.exit_code == 0, out.output
    assert '"entity": "layer"' in out.output
    assert '"id": "l1"' in out.output


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
