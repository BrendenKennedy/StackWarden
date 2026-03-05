"""Tests for build-level file locking."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from stackwarden.domain.locking import (
    _sanitize_filename,
    acquire_lock,
    compute_variant_hash,
)


class TestVariantHash:
    def test_empty_variants(self):
        assert compute_variant_hash(None) == ""
        assert compute_variant_hash({}) == ""

    def test_deterministic(self):
        v = {"precision": "bf16", "batch_size": "32"}
        h1 = compute_variant_hash(v)
        h2 = compute_variant_hash(v)
        assert h1 == h2
        assert len(h1) == 12

    def test_order_independent(self):
        v1 = {"a": "1", "b": "2"}
        v2 = {"b": "2", "a": "1"}
        assert compute_variant_hash(v1) == compute_variant_hash(v2)

    def test_different_values_different_hash(self):
        assert compute_variant_hash({"a": "1"}) != compute_variant_hash({"a": "2"})


class TestSanitizeFilename:
    def test_replaces_colons(self):
        assert ":" not in _sanitize_filename("a:b:c")

    def test_replaces_slashes(self):
        assert "/" not in _sanitize_filename("a/b/c")

    def test_replaces_spaces(self):
        assert " " not in _sanitize_filename("a b c")

    def test_replaces_equals(self):
        assert "=" not in _sanitize_filename("a=b")

    def test_preserves_safe_chars(self):
        safe = "abc-def_ghi.123"
        assert _sanitize_filename(safe) == safe

    def test_complex_key(self):
        key = "x86_cuda:llm_vllm:abc123def456"
        result = _sanitize_filename(key)
        assert result == "x86_cuda_llm_vllm_abc123def456"


class TestAcquireLock:
    def test_basic_acquire_release(self, tmp_path):
        with patch("stackwarden.domain.locking.get_locks_root", return_value=tmp_path):
            with acquire_lock("profile", "stack"):
                lock_files = list(tmp_path.glob("*.lock"))
                assert len(lock_files) == 1

    def test_lock_serializes_access(self, tmp_path):
        """Two threads acquiring the same lock should not overlap."""
        with patch("stackwarden.domain.locking.get_locks_root", return_value=tmp_path):
            results = []

            def worker(idx):
                with acquire_lock("p", "s", timeout=10):
                    results.append(f"enter-{idx}")
                    time.sleep(0.05)
                    results.append(f"exit-{idx}")

            t1 = threading.Thread(target=worker, args=(1,))
            t2 = threading.Thread(target=worker, args=(2,))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            enter_1 = results.index("enter-1")
            exit_1 = results.index("exit-1")
            enter_2 = results.index("enter-2")
            exit_2 = results.index("exit-2")
            # One must complete before the other starts
            assert exit_1 < enter_2 or exit_2 < enter_1

    def test_different_keys_no_contention(self, tmp_path):
        with patch("stackwarden.domain.locking.get_locks_root", return_value=tmp_path):
            results = []

            def worker(profile_id, idx):
                with acquire_lock(profile_id, "s"):
                    results.append(idx)

            t1 = threading.Thread(target=worker, args=("p1", 1))
            t2 = threading.Thread(target=worker, args=("p2", 2))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            assert set(results) == {1, 2}

    def test_creates_locks_directory(self, tmp_path):
        lock_dir = tmp_path / "locks"
        with patch("stackwarden.domain.locking.get_locks_root", return_value=lock_dir):
            with acquire_lock("p", "s"):
                assert lock_dir.exists()
