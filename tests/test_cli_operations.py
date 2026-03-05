from __future__ import annotations

from typer.testing import CliRunner

from stackwarden.cli import app


class _Rec:
    def __init__(self, status: str) -> None:
        self.status = type("S", (), {"value": status})()
        self.profile_id = "p1"
        self.stack_id = "s1"
        self.tag = "t1"
        self.fingerprint = "f" * 64
        self.created_at = None


class _Catalog:
    def search_artifacts(self, status: str | None = None):
        rows = [_Rec("built"), _Rec("stale"), _Rec("failed")]
        if status:
            return [r for r in rows if r.status.value == status]
        return rows

    def prune_by_status(self, _status):
        return 1

    def find_unused(self, force: bool = False):
        return []

    def count_protected(self):
        return 0


def test_status_and_prune_json(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("stackwarden.cli.get_catalog", lambda: _Catalog())
    status = runner.invoke(app, ["status", "--json"])
    assert status.exit_code == 0, status.output
    assert '"total": 3' in status.output

    prune = runner.invoke(app, ["prune", "--json"])
    assert prune.exit_code == 0, prune.output
    assert '"pruned"' in prune.output
