from __future__ import annotations

from typer.testing import CliRunner

from stacksmith.cli import app


class _FakePlan:
    plan_id = "p"
    profile_id = "p1"
    stack_id = "s1"
    decision = type(
        "Decision",
        (),
        {"base_image": "python:3.11", "builder": "overlay", "warnings": [], "rationale": None},
    )()
    artifact = type("Artifact", (), {"tag": "x:y", "fingerprint": "f" * 64})()
    steps: list = []

    def to_json(self):
        return {"stack_id": self.stack_id}


class _CompatReport:
    compatible = True
    errors: list = []
    warnings: list = []
    info: list = []

    def model_dump(self, mode: str = "json"):
        return {"compatible": True}


def test_plan_uses_strict_default_from_env(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("STACKSMITH_COMPAT_STRICT", "1")
    monkeypatch.setattr("stacksmith.config.load_profile", lambda _id: object())
    monkeypatch.setattr("stacksmith.config.load_stack", lambda _id: type("S", (), {"blocks": []})())
    monkeypatch.setattr("stacksmith.config.load_block", lambda _id: object())
    seen: dict[str, bool] = {}

    def _resolve(*_args, **kwargs):
        seen["strict_mode"] = bool(kwargs.get("strict_mode"))
        return _FakePlan()

    monkeypatch.setattr("stacksmith.resolvers.resolver.resolve", _resolve)
    out = runner.invoke(app, ["plan", "--profile", "p1", "--stack", "s1", "--json"])
    assert out.exit_code == 0, out.output
    assert seen["strict_mode"] is True


def test_check_uses_env_default_and_can_override(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("STACKSMITH_COMPAT_STRICT", "1")
    monkeypatch.setattr("stacksmith.config.load_profile", lambda _id: object())
    monkeypatch.setattr("stacksmith.config.load_stack", lambda _id: type("S", (), {"blocks": []})())
    monkeypatch.setattr("stacksmith.config.load_block", lambda _id: object())
    seen: list[bool] = []

    def _evaluate(*_args, **kwargs):
        seen.append(bool(kwargs.get("strict_mode")))
        return _CompatReport()

    monkeypatch.setattr("stacksmith.resolvers.compatibility.evaluate_compatibility", _evaluate)

    out_default = runner.invoke(app, ["check", "--profile", "p1", "--stack", "s1", "--json"])
    assert out_default.exit_code == 0, out_default.output

    out_override = runner.invoke(
        app,
        ["check", "--profile", "p1", "--stack", "s1", "--no-strict", "--json"],
    )
    assert out_override.exit_code == 0, out_override.output
    assert seen == [True, False]
