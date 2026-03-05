"""Entity-first CLI command coverage."""

from __future__ import annotations

import yaml
from typer.testing import CliRunner

from stackwarden.cli import app


def _write_yaml(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_profiles_entity_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    runner = CliRunner()

    profile_file = tmp_path / "input-profile.yaml"
    _write_yaml(
        profile_file,
        {
            "schema_version": 1,
            "id": "entity_profile",
            "display_name": "Entity Profile",
            "arch": "amd64",
            "os": "linux",
            "container_runtime": "runc",
            "cuda": {"major": 12, "minor": 4, "variant": "cuda12.4"},
            "gpu": {"vendor": "nvidia", "family": "test"},
            "capabilities": [],
            "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 10}],
            "constraints": {"disallow": {}, "require": {}},
            "defaults": {"python": "3.10", "user": "root", "workdir": "/workspace"},
        },
    )

    create_result = runner.invoke(app, ["profiles", "create", "--file", str(profile_file)])
    assert create_result.exit_code == 0, create_result.output

    list_result = runner.invoke(app, ["profiles", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert "Deprecated command alias" in list_result.output
    assert "entity_profile" in list_result.output

    show_result = runner.invoke(app, ["profiles", "show", "--id", "entity_profile", "--json"])
    assert show_result.exit_code == 0, show_result.output
    assert '"id": "entity_profile"' in show_result.output

    edited_file = tmp_path / "edited-profile.yaml"
    _write_yaml(
        edited_file,
        {
            "schema_version": 1,
            "id": "entity_profile",
            "display_name": "Entity Profile Updated",
            "arch": "amd64",
            "os": "linux",
            "container_runtime": "runc",
            "cuda": {"major": 12, "minor": 4, "variant": "cuda12.4"},
            "gpu": {"vendor": "nvidia", "family": "test"},
            "capabilities": [],
            "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 10}],
            "constraints": {"disallow": {}, "require": {}},
            "defaults": {"python": "3.10", "user": "root", "workdir": "/workspace"},
        },
    )
    edit_result = runner.invoke(
        app,
        ["profiles", "edit", "--id", "entity_profile", "--file", str(edited_file), "--json"],
    )
    assert edit_result.exit_code == 0, edit_result.output


def test_stacks_and_blocks_entity_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    runner = CliRunner()

    block_file = tmp_path / "input-block.yaml"
    _write_yaml(
        block_file,
        {
            "kind": "block",
            "schema_version": 1,
            "id": "entity_block",
            "display_name": "Entity Block",
            "block_kind": "api",
            "components": {
                "base_role": "python",
                "pip": [{"name": "fastapi", "version": "==0.115.*"}],
                "apt": [],
            },
            "env": [],
            "ports": [8000],
            "entrypoint": {"cmd": ["python", "-m", "uvicorn", "app.main:app"]},
            "files": {"copy": []},
            "variants": {},
        },
    )
    create_block = runner.invoke(app, ["blocks", "create", "--file", str(block_file)])
    assert create_block.exit_code == 0, create_block.output

    block_show = runner.invoke(app, ["blocks", "show", "--id", "entity_block", "--json"])
    assert block_show.exit_code == 0, block_show.output
    assert '"id": "entity_block"' in block_show.output

    stack_file = tmp_path / "input-stack.yaml"
    _write_yaml(
        stack_file,
        {
            "kind": "stack_recipe",
            "schema_version": 1,
            "id": "entity_stack",
            "display_name": "Entity Stack",
            "blocks": ["entity_block"],
            "build_strategy": "overlay",
            "components": {
                "base_role": "python",
                "pip": [{"name": "fastapi", "version": "==0.115.*"}],
                "apt": [],
            },
            "env": [],
            "ports": [8000],
            "entrypoint": {"cmd": ["python", "-m", "uvicorn", "app.main:app"]},
            "files": {"copy": []},
            "variants": {},
        },
    )
    create_stack = runner.invoke(app, ["stacks", "create", "--file", str(stack_file)])
    assert create_stack.exit_code == 0, create_stack.output

    stack_list = runner.invoke(app, ["stacks", "list"])
    assert stack_list.exit_code == 0, stack_list.output
    assert "Deprecated command alias" in stack_list.output
    assert "entity_stack" in stack_list.output

    stack_show = runner.invoke(app, ["stacks", "show", "--id", "entity_stack", "--json"])
    assert stack_show.exit_code == 0, stack_show.output
    assert '"id": "entity_stack"' in stack_show.output


def test_check_and_migrate_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STACKWARDEN_TUPLE_LAYER_MODE", "off")
    runner = CliRunner()

    profile_file = tmp_path / "input-profile.yaml"
    _write_yaml(
        profile_file,
        {
            "schema_version": 1,
            "id": "check_profile",
            "display_name": "Check Profile",
            "arch": "amd64",
            "os": "linux",
            "container_runtime": "nvidia",
            "cuda": {"major": 12, "minor": 4, "variant": "cuda12.4"},
            "gpu": {"vendor": "nvidia", "family": "test"},
            "capabilities": ["cuda"],
            "base_candidates": [{"name": "python", "tags": ["3.12-slim"], "score_bias": 10}],
            "constraints": {"disallow": {}, "require": {}},
            "defaults": {"python": "3.10", "user": "root", "workdir": "/workspace"},
        },
    )
    stack_file = tmp_path / "input-stack.yaml"
    block_file = tmp_path / "input-block.yaml"
    _write_yaml(
        block_file,
        {
            "kind": "block",
            "schema_version": 1,
            "id": "check_block",
            "display_name": "Check Block",
            "components": {
                "base_role": "python",
                "pip": [{"name": "fastapi", "version": "==0.115.*"}],
                "apt": [],
            },
            "env": [],
            "ports": [8000],
            "entrypoint": {"cmd": ["python", "-m", "uvicorn", "app.main:app"]},
            "files": {"copy": []},
            "variants": {},
        },
    )
    _write_yaml(
        stack_file,
        {
            "kind": "stack_recipe",
            "schema_version": 1,
            "id": "check_stack",
            "display_name": "Check Stack",
            "blocks": ["check_block"],
            "build_strategy": "overlay",
            "components": {"base_role": "python", "pip": [], "apt": []},
            "env": [],
            "ports": [8000],
            "entrypoint": {"cmd": ["python", "-m", "uvicorn", "app.main:app"]},
            "files": {"copy": []},
            "variants": {},
        },
    )
    assert runner.invoke(app, ["profiles", "create", "--file", str(profile_file)]).exit_code == 0
    assert runner.invoke(app, ["blocks", "create", "--file", str(block_file)]).exit_code == 0
    assert runner.invoke(app, ["stacks", "create", "--file", str(stack_file)]).exit_code == 0

    check_result = runner.invoke(
        app,
        ["check", "--profile", "check_profile", "--stack", "check_stack", "--json"],
    )
    assert check_result.exit_code == 0, check_result.output
    assert '"compatible": true' in check_result.output

    migrate_result = runner.invoke(app, ["migrate", "v1-to-v2"])
    assert migrate_result.exit_code == 0, migrate_result.output
    assert "would migrate" in migrate_result.output
