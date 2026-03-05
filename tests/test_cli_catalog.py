from __future__ import annotations

from typer.testing import CliRunner

from stackwarden.cli import app


class _Catalog:
    def search_artifacts(self, **kwargs):
        return []


def test_catalog_search_empty(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stackwarden.cli.get_catalog", lambda: _Catalog())
    out = runner.invoke(app, ["catalog", "search"])
    assert out.exit_code == 0, out.output
    assert "No artifacts found" in out.output
