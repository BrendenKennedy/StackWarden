from __future__ import annotations

from typer.testing import CliRunner

from stacksmith.cli import app


class _Record:
    profile_id = "p1"
    stack_id = "my_stack"
    fingerprint = "f" * 64


class _Catalog:
    def get_artifact_by_tag(self, _tag: str):
        return _Record()


def test_export_run_cpu_runtime_skips_default_gpus(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stacksmith.cli._get_catalog", lambda: _Catalog())
    monkeypatch.setattr("stacksmith.cli._artifact_runtime_and_ports", lambda _r: ("runc", [8080]))

    out = runner.invoke(app, ["export", "run", "my:tag"])
    assert out.exit_code == 0, out.output
    assert "--gpus" not in out.output
    assert "-p 8080:8080" in out.output


def test_export_compose_nvidia_runtime_includes_gpu_defaults(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stacksmith.cli._get_catalog", lambda: _Catalog())
    monkeypatch.setattr("stacksmith.cli._artifact_runtime_and_ports", lambda _r: ("nvidia", [8000]))

    out = runner.invoke(app, ["export", "compose", "my:tag"])
    assert out.exit_code == 0, out.output
    assert "runtime: nvidia" in out.output
    assert "count: all" in out.output
    assert "8000:8000" in out.output


def test_export_compose_cpu_runtime_omits_gpu_reservations(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stacksmith.cli._get_catalog", lambda: _Catalog())
    monkeypatch.setattr("stacksmith.cli._artifact_runtime_and_ports", lambda _r: ("runc", [8000]))

    out = runner.invoke(app, ["export", "compose", "my:tag"])
    assert out.exit_code == 0, out.output
    assert "runtime: nvidia" not in out.output
    assert "devices:" not in out.output
