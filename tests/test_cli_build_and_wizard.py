from __future__ import annotations

from typer.testing import CliRunner

from stacksmith.cli import app


class _Sel:
    profile_id = "p1"
    stack_id = "s1"
    variants = {}
    flags = type("F", (), {"rebuild": False, "upgrade_base": False, "immutable": False, "no_hooks": True, "explain": False})()


class _WizResult:
    selection = _Sel()
    command = "stacksmith ensure --profile p1 --stack s1"
    executed = False
    tag = None

    def model_dump_json(self, indent: int = 2):
        return '{"selection":{"profile_id":"p1","stack_id":"s1"}}'


def test_wizard_defaults_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stacksmith.ui.wizard.run_wizard", lambda **_: _WizResult())
    monkeypatch.setattr(
        "stacksmith.config.AppConfig.load",
        lambda: type("C", (), {"default_profile": None, "log_dir": None})(),
    )
    out = runner.invoke(app, ["wizard", "--defaults", "--json"])
    assert out.exit_code == 0, out.output
    assert '"profile_id": "p1"' in out.output
