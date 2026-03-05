from __future__ import annotations

import builtins

import pytest

from stackwarden.web_entry import main


def test_web_entrypoint_shows_actionable_message_when_web_extras_missing(monkeypatch):
    original_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "stackwarden.web.app":
            raise ModuleNotFoundError("No module named 'fastapi'", name="fastapi")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(SystemExit) as exc:
        main()
    assert "stackwarden[web]" in str(exc.value)
