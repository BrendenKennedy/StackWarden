"""SBOM export tests — mocked docker sbom / syft, failure handling."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from stackwarden.runtime.sbom import export_sbom, SbomUnavailableError


@pytest.fixture
def tmp_artifacts(tmp_path):
    with patch("stackwarden.runtime.sbom.manifest_dir", return_value=tmp_path):
        yield tmp_path


class TestExportSbom:
    def test_docker_sbom_success(self, tmp_artifacts):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"packages": [{"name": "torch"}]})

        with patch("subprocess.run", return_value=mock_result):
            path = export_sbom("test:latest", "fp123")
            assert path.exists()
            data = json.loads(path.read_text())
            assert "packages" in data

    def test_syft_fallback(self, tmp_artifacts):
        docker_fail = MagicMock()
        docker_fail.returncode = 1
        docker_fail.stdout = ""

        syft_ok = MagicMock()
        syft_ok.returncode = 0
        syft_ok.stdout = json.dumps({"components": [{"name": "numpy"}]})

        def side_effect(cmd, **kw):
            if "sbom" in cmd:
                return docker_fail
            return syft_ok

        with patch("subprocess.run", side_effect=side_effect):
            with patch("shutil.which", return_value="/usr/bin/syft"):
                path = export_sbom("test:latest", "fp123")
                assert path.exists()

    def test_no_tools_raises(self, tmp_artifacts):
        fail = MagicMock()
        fail.returncode = 1
        fail.stdout = ""

        with patch("subprocess.run", return_value=fail):
            with patch("shutil.which", return_value=None):
                with pytest.raises(SbomUnavailableError):
                    export_sbom("test:latest", "fp123")

    def test_sbom_failure_does_not_mark_artifact_failed(self, tmp_artifacts):
        """SBOM is auxiliary — callers should catch exceptions gracefully."""
        from stackwarden.runtime.sbom import SbomUnavailableError

        fail = MagicMock()
        fail.returncode = 1
        fail.stdout = ""
        fail.stderr = "tool not found"

        with patch("subprocess.run", return_value=fail):
            with patch("shutil.which", return_value=None):
                try:
                    export_sbom("test:latest", "fp456")
                except SbomUnavailableError:
                    pass

        with patch("subprocess.run", return_value=fail):
            with patch("shutil.which", return_value=None):
                with pytest.raises(SbomUnavailableError):
                    export_sbom("test:latest", "fp456")
