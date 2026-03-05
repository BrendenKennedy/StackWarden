from __future__ import annotations

from typer.testing import CliRunner

from stackwarden.cli import app


class _Report:
    ok = True
    errors: list[str] = []
    warnings: list[str] = []
    facts: dict[str, str] = {}

    def model_dump_json(self, indent: int = 2):
        return '{"ok": true}'


class _Catalog:
    pass


def test_verify_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stackwarden.cli._get_catalog", lambda: _Catalog())
    monkeypatch.setattr("stackwarden.runtime.docker_client.DockerClient", lambda: object())
    monkeypatch.setattr("stackwarden.domain.verify.verify_artifact", lambda *_, **__: _Report())
    out = runner.invoke(app, ["verify", "my-tag", "--json"])
    assert out.exit_code == 0, out.output
    assert '"ok": true' in out.output
