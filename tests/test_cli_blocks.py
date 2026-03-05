"""CLI coverage for block composition commands."""

from __future__ import annotations

import yaml
from typer.testing import CliRunner

from stackwarden.cli import app


def _write_yaml(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _seed_composed_stack_data(root) -> None:
    _write_yaml(
        root / "profiles" / "test_profile.yaml",
        {
            "schema_version": 1,
            "id": "test_profile",
            "display_name": "Test Profile",
            "arch": "amd64",
            "os": "linux",
            "os_family": "ubuntu",
            "os_version": "22.04",
            "os_family_id": "ubuntu",
            "os_version_id": "ubuntu_22_04",
            "container_runtime": "nvidia",
            "cuda": {"major": 12, "minor": 4, "variant": "cuda12.4"},
            "gpu": {
                "vendor": "nvidia",
                "family": "ampere",
                "vendor_id": "nvidia",
                "family_id": "ampere",
            },
            "capabilities": [],
            "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 10}],
        },
    )
    _write_yaml(
        root / "blocks" / "runtime.yaml",
        {
            "kind": "block",
            "schema_version": 1,
            "id": "runtime",
            "display_name": "Runtime",
            "build_strategy": "overlay",
            "components": {"base_role": "python"},
            "entrypoint": {"cmd": ["python", "main.py"]},
        },
    )
    _write_yaml(
        root / "stacks" / "recipe.yaml",
        {
            "kind": "stack_recipe",
            "schema_version": 1,
            "id": "recipe",
            "display_name": "Recipe",
            "task": "custom",
            "serve": "python_api",
            "api": "none",
            "blocks": ["runtime"],
        },
    )


def test_list_blocks_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    _seed_composed_stack_data(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["list", "blocks"])
    assert result.exit_code == 0, result.output
    assert "runtime" in result.output


def test_inspect_block_cli_json(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    _seed_composed_stack_data(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["inspect-block", "--id", "runtime", "--json"])
    assert result.exit_code == 0, result.output
    assert '"id": "runtime"' in result.output


def test_compose_cli_json(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    _seed_composed_stack_data(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["compose", "--stack", "recipe", "--json"])
    assert result.exit_code == 0, result.output
    assert '"id": "recipe"' in result.output
    assert '"base_role": "python"' in result.output


def test_plan_cli_with_recipe_stack(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    _seed_composed_stack_data(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "--profile", "test_profile", "--stack", "recipe", "--json"],
    )
    assert result.exit_code == 0, result.output
    assert '"stack_id": "recipe"' in result.output

