"""Tests for stackwarden.builders.pull — _split_image_ref and build_pull."""

from __future__ import annotations

import pytest

from stackwarden.builders.pull import _split_image_ref


class TestSplitImageRef:
    def test_simple_tag(self):
        assert _split_image_ref("ubuntu:22.04") == ("ubuntu", "22.04")

    def test_no_tag_defaults_to_latest(self):
        assert _split_image_ref("ubuntu") == ("ubuntu", "latest")

    def test_registry_with_port(self):
        assert _split_image_ref("registry:5000/myimage:v1") == ("registry:5000/myimage", "v1")

    def test_registry_with_port_no_tag(self):
        assert _split_image_ref("registry:5000/myimage") == ("registry:5000/myimage", "latest")

    def test_digest_reference(self):
        repo, digest = _split_image_ref("ubuntu@sha256:abc123")
        assert repo == "ubuntu"
        assert digest == "@sha256:abc123"

    def test_nested_registry_path(self):
        assert _split_image_ref("nvcr.io/nvidia/pytorch:24.06-py3") == (
            "nvcr.io/nvidia/pytorch",
            "24.06-py3",
        )
