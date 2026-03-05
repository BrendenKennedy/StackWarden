"""Hook protocol, mock hook pass/fail, and failure handling tests."""

from __future__ import annotations

import pytest

from stackwarden.hooks.protocol import HookResult, PostBuildHook


class MockPassHook:
    name = "mock_pass"

    def run(self, tag, profile, stack):
        return HookResult(success=True)


class MockFailHook:
    name = "mock_fail"

    def run(self, tag, profile, stack):
        return HookResult(success=False, logs="something broke")


class MockWarnHook:
    name = "mock_warn"

    def run(self, tag, profile, stack):
        return HookResult(success=True, warnings=["minor issue"])


class TestHookResult:
    def test_success(self):
        r = HookResult(success=True)
        assert r.success
        assert r.logs == ""
        assert r.warnings == []

    def test_failure_with_logs(self):
        r = HookResult(success=False, logs="import failed")
        assert not r.success
        assert "import" in r.logs


class TestHookProtocol:
    def test_pass_hook_satisfies_protocol(self):
        hook = MockPassHook()
        assert isinstance(hook, PostBuildHook)

    def test_fail_hook_satisfies_protocol(self):
        hook = MockFailHook()
        assert isinstance(hook, PostBuildHook)

    def test_hooks_receive_tag_not_mutable_handle(self):
        hook = MockPassHook()
        result = hook.run("local/stackwarden:test", None, None)
        assert result.success


class MockExceptionHook:
    name = "mock_exception"

    def run(self, tag, profile, stack):
        raise RuntimeError("hook crashed unexpectedly")


class TestHookRegistry:
    def test_builtin_hooks_loaded(self):
        from stackwarden.hooks import get_hooks
        hooks = get_hooks()
        names = [h.name for h in hooks]
        assert "import_smoke" in names
        assert "cuda_visibility" in names

    def test_warn_hook_returns_warnings(self):
        hook = MockWarnHook()
        result = hook.run("test:tag", None, None)
        assert result.success
        assert len(result.warnings) == 1
        assert "minor issue" in result.warnings[0]


class TestHookExceptionHandling:
    def test_hook_exception_raises(self):
        """MockExceptionHook should raise RuntimeError."""
        hook = MockExceptionHook()
        with pytest.raises(RuntimeError, match="hook crashed"):
            hook.run("test:tag", None, None)

    def test_runner_catches_hook_exception(self, tmp_path):
        """The plan_executor _run_hooks catches per-hook exceptions
        and marks the artifact as failed instead of crashing."""
        from unittest.mock import patch, MagicMock
        from stackwarden.domain.enums import ArtifactStatus
        from stackwarden.domain.models import ArtifactRecord

        record = MagicMock(spec=ArtifactRecord)
        record.tag = "test:tag"
        record.status = ArtifactStatus.BUILT

        catalog = MagicMock()
        exception_hook = MockExceptionHook()

        with patch("stackwarden.hooks.get_hooks", return_value=[exception_hook]):
            from stackwarden.builders.plan_executor import _run_hooks
            _run_hooks(record, None, None, catalog)

        assert record.status == ArtifactStatus.FAILED
        assert "hook crashed" in record.error_detail
        catalog.update_artifact.assert_called_once()
