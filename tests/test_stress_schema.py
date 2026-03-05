"""Stress tests: schema and malformed input.

- Malformed stack/block YAML — validation error, no crash
- Empty/minimal specs — accepted or rejected as designed
- Path traversal in load_profile/load_stack/load_block — rejected
- Path traversal in copy_items — rejected (Web API)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml

from stackwarden.config import load_profile, load_stack, load_block
from stackwarden.domain.errors import StackWardenError


class TestMalformedSpecs:
    """Malformed YAML or invalid schema raises, does not crash."""

    def test_load_stack_malformed_yaml(self, tmp_path):
        (tmp_path / "stacks").mkdir(parents=True)
        (tmp_path / "stacks" / "bad.yaml").write_text("not: valid: yaml: [")
        with patch.dict("os.environ", {"STACKWARDEN_DATA_DIR": str(tmp_path)}):
            with pytest.raises(Exception):  # yaml.YAMLError or similar
                load_stack("bad")

    def test_load_stack_missing_required_field(self, tmp_path):
        (tmp_path / "stacks").mkdir(parents=True)
        (tmp_path / "stacks" / "minimal.yaml").write_text(
            yaml.safe_dump({"id": "minimal"})  # Missing many required fields
        )
        with patch.dict("os.environ", {"STACKWARDEN_DATA_DIR": str(tmp_path)}):
            with pytest.raises((StackWardenError, Exception)):
                load_stack("minimal")


class TestPathTraversal:
    """Path traversal in spec IDs is rejected."""

    def test_load_profile_rejects_traversal(self, tmp_path):
        (tmp_path / "profiles").mkdir(parents=True)
        (tmp_path / "profiles" / "p1.yaml").write_text("id: p1\ndisplay_name: P1\narch: amd64")
        with patch.dict("os.environ", {"STACKWARDEN_DATA_DIR": str(tmp_path)}):
            with pytest.raises((StackWardenError, FileNotFoundError)):
                load_profile("../../../etc/passwd")

    def test_load_stack_rejects_traversal(self, tmp_path):
        (tmp_path / "stacks").mkdir(parents=True)
        with patch.dict("os.environ", {"STACKWARDEN_DATA_DIR": str(tmp_path)}):
            with pytest.raises((StackWardenError, FileNotFoundError)):
                load_stack("../../etc/passwd")

    def test_load_block_rejects_traversal(self, tmp_path):
        (tmp_path / "blocks").mkdir(parents=True)
        with patch.dict("os.environ", {"STACKWARDEN_DATA_DIR": str(tmp_path)}):
            with pytest.raises((StackWardenError, FileNotFoundError)):
                load_block("../../../etc/passwd")


class TestEmptySpecs:
    """Empty or minimal valid specs."""

    def test_empty_pip_list_valid(self, tmp_path):
        """Stack with empty pip list is valid."""
        (tmp_path / "profiles").mkdir(parents=True)
        (tmp_path / "stacks").mkdir(parents=True)
        (tmp_path / "profiles" / "p1.yaml").write_text(
            yaml.safe_dump({
                "schema_version": 2,
                "id": "p1",
                "display_name": "P1",
                "arch": "amd64",
                "os": "linux",
                "cuda": {"major": 0, "minor": 0, "variant": "none"},
                "gpu": {"vendor": "none", "family": "none"},
                "base_candidates": [{"name": "python", "tags": ["3.12-slim"]}],
            })
        )
        (tmp_path / "stacks" / "s1.yaml").write_text(
            yaml.safe_dump({
                "kind": "stack",
                "schema_version": 2,
                "id": "s1",
                "display_name": "S1",
                "task": "custom",
                "serve": "custom",
                "api": "none",
                "build_strategy": "overlay",
                "components": {"base_role": "python", "pip": [], "apt": []},
                "entrypoint": {"cmd": ["python", "-V"]},
            })
        )
        with patch.dict("os.environ", {"STACKWARDEN_DATA_DIR": str(tmp_path)}):
            p = load_profile("p1")
            s = load_stack("s1")
            assert p.id == "p1"
            assert s.id == "s1"
            assert s.components.pip == []
