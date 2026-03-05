from __future__ import annotations

import yaml
from typer.testing import CliRunner

from stackwarden.cli import app


def test_migrate_preview(monkeypatch, tmp_path):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "hardware_catalog.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "revision": 1}),
        encoding="utf-8",
    )
    (tmp_path / "profiles").mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "p.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "id": "p1",
                "display_name": "P1",
                "arch": "amd64",
                "os": "linux",
                "container_runtime": "nvidia",
                "cuda": {"major": 12, "minor": 4, "variant": "runtime"},
                "gpu": {"vendor": "nvidia", "family": "ampere"},
                "base_candidates": [{"name": "python", "tags": ["3.12-slim"]}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = CliRunner().invoke(app, ["migrate", "v1-to-v2"])
    assert out.exit_code == 0, out.output
    assert "would migrate" in out.output
