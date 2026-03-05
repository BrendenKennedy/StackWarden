"""Unit tests for buildx command assembly and OOM retry logic."""

from __future__ import annotations

from stackwarden.runtime import buildx


class _FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def readline(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        return ""


class _FakeProcess:
    def __init__(self, lines: list[str], returncode: int) -> None:
        self.stdout = _FakeStdout(lines)
        self._returncode = returncode
        self.killed = False

    @property
    def returncode(self) -> int:
        return self._returncode

    def poll(self):
        if self.stdout._lines:  # noqa: SLF001
            return None
        return self._returncode

    def kill(self) -> None:
        self.killed = True
        self._returncode = 124

    def wait(self, timeout: int | None = None) -> int:
        return self._returncode


def test_build_includes_extra_flags(monkeypatch):
    calls: list[list[str]] = []

    def _fake_popen(cmd, **_kwargs):
        calls.append(list(cmd))
        return _FakeProcess(["ok\n"], returncode=0)

    monkeypatch.setattr("stackwarden.runtime.buildx.subprocess.Popen", _fake_popen)

    buildx.build(
        context_dir=".",
        tags=["local/test:1"],
        build_args={"STACKWARDEN_BUILD_JOBS": "4"},
        extra_flags=["--progress=plain"],
    )
    assert calls
    cmd = calls[0]
    assert "--progress=plain" in cmd


def test_build_retries_when_oom(monkeypatch):
    calls: list[list[str]] = []

    def _fake_popen(cmd, **_kwargs):
        calls.append(list(cmd))
        if len(calls) == 1:
            return _FakeProcess(["killed: out of memory\n"], returncode=1)
        return _FakeProcess(["ok\n"], returncode=0)

    monkeypatch.setattr("stackwarden.runtime.buildx.subprocess.Popen", _fake_popen)

    buildx.build(
        context_dir=".",
        tags=["local/test:1"],
        build_args={"STACKWARDEN_BUILD_JOBS": "8"},
    )
    assert len(calls) == 2
    assert any("STACKWARDEN_BUILD_JOBS=8" in token for token in calls[0])
    assert any("STACKWARDEN_BUILD_JOBS=4" in token for token in calls[1])
