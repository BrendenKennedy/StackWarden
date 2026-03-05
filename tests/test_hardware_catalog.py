from __future__ import annotations

import textwrap
from types import SimpleNamespace

from stackwarden.domain.hardware_catalog import load_hardware_catalog, reconcile_detected_fields
from stackwarden.web.services.host_detection_probes import infer_gpu_family


def test_default_catalog_has_core_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    catalog = load_hardware_catalog()
    assert any(i.id == "amd64" for i in catalog.arch)
    assert any(i.id == "ppc64le" for i in catalog.arch)
    assert any(i.id == "nvidia" for i in catalog.gpu_vendor)
    assert any(i.id == "ubuntu_22_04" for i in catalog.os_version)
    assert any(i.id == "debian_12" for i in catalog.os_version)
    assert any(i.id == "rocky_9" for i in catalog.os_version)
    assert any(i.id == "nvidia_h100" for i in catalog.gpu_model)
    assert any(i.id == "amd_mi300x" for i in catalog.gpu_model)
    assert any(i.id == "intel_flex_170" for i in catalog.gpu_model)


def test_reconcile_detected_fields_maps_known_values(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    payload = {
        "arch": "x86_64",
        "os_family": "ubuntu",
        "container_runtime": "nvidia",
        "gpu": {"vendor": "NVIDIA", "family": "hopper"},
    }
    resolved, matched_by, unmatched = reconcile_detected_fields(payload)
    assert resolved["arch_id"] == "amd64"
    assert resolved["gpu_vendor_id"] == "nvidia"
    assert resolved["gpu_family_id"] == "hopper"
    assert matched_by["gpu_vendor_id"] in {"exact", "alias"}
    assert unmatched == []


def test_reconcile_detected_fields_maps_os_version_and_gpu_model(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "hardware_catalog.yaml").write_text(
        textwrap.dedent(
            """
            schema_version: 1
            revision: 1
            arch: []
            os_family: []
            os_version:
              - id: ubuntu_22_04
                label: "Ubuntu 22.04"
                aliases: ["22.04"]
            container_runtime: []
            gpu_vendor: []
            gpu_family: []
            gpu_model:
              - id: h100_sxm
                label: "NVIDIA H100 SXM"
                aliases: ["nvidia h100 80gb hbm3"]
            """
        ).strip()
    )
    payload = {
        "os_version": "22.04",
        "gpu_model": "NVIDIA H100 80GB HBM3",
    }
    resolved, matched_by, unmatched = reconcile_detected_fields(payload)
    assert resolved["os_version_id"] == "ubuntu_22_04"
    assert resolved["gpu_model_id"] == "h100_sxm"
    assert matched_by["os_version_id"] == "alias"
    assert matched_by["gpu_model_id"] == "alias"
    assert unmatched == []


def test_reconcile_detected_fields_infers_gpu_model_from_long_name(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    payload = {
        "gpu_model": "NVIDIA GB10 [GeForce RTX 5090 Laptop GPU]",
    }
    resolved, matched_by, unmatched = reconcile_detected_fields(payload)
    assert resolved["gpu_model_id"] == "nvidia_gb10"
    assert matched_by["gpu_model_id"] == "inferred"
    assert unmatched == []


def test_infer_gpu_family_blackwell_variants():
    assert infer_gpu_family("NVIDIA GB10") == "blackwell"
    assert infer_gpu_family("NVIDIA RTX 5090") == "blackwell"


def test_reconcile_detected_fields_handles_gpu_object_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    payload = {
        "gpu": SimpleNamespace(vendor="nvidia", family="blackwell"),
    }
    resolved, matched_by, unmatched = reconcile_detected_fields(payload)
    assert resolved["gpu_vendor_id"] == "nvidia"
    assert resolved["gpu_family_id"] == "blackwell"
    assert matched_by["gpu_vendor_id"] in {"exact", "alias"}
    assert matched_by["gpu_family_id"] in {"exact", "alias"}
    assert unmatched == []
