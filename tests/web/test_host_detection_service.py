from __future__ import annotations

from stacksmith.web.schemas import DetectionProbeDTO
from stacksmith.web.services import host_detection as hd
from stacksmith.web.services.host_detection_probes import ProbeContext, ProbeResult, ProbeSpec, route_os_branch


def _probe_result(name: str, payload: dict) -> ProbeResult:
    return ProbeResult(
        probe=DetectionProbeDTO(name=name, status="ok", message="", duration_ms=1),
        payload=payload,
    )


def test_detect_server_hints_chain_order_and_skip(monkeypatch):
    calls: list[str] = []

    def fake_run_probe(name, _fn, context):
        calls.append(name)
        if name == "bootstrap_invariants":
            return _probe_result(
                name,
                {
                    "arch": "amd64",
                    "os": "linux",
                    "os_family": "ubuntu",
                    "os_version": "22.04",
                    "confidence": {
                        "arch": "detected",
                        "os": "detected",
                        "os_family": "detected",
                        "os_version": "detected",
                    },
                },
            )
        if name == "execution_context":
            return _probe_result(
                name,
                {
                    "context": {
                        "docker_available": True,
                        "docker_socket_present": True,
                        "nvidia_smi_available": False,
                        "in_container": False,
                    }
                },
            )
        if name == "os_router":
            context.os_branch = "debian_ubuntu"
            return _probe_result(name, {})
        if name == "host_resources":
            return _probe_result(
                name,
                {
                    "cpu_model": "AMD EPYC",
                    "cpu_cores_logical": 32,
                    "cpu_cores_physical": 16,
                    "memory_gb_total": 128.0,
                    "disk_gb_total": 512.0,
                    "confidence": {
                        "cpu_model": "detected",
                        "cpu_cores_logical": "detected",
                        "cpu_cores_physical": "detected",
                        "memory_gb_total": "detected",
                        "disk_gb_total": "detected",
                    },
                },
            )
        if name == "docker":
            return _probe_result(name, {"container_runtime": "runc", "confidence": {"container_runtime": "detected"}})
        raise AssertionError(f"unexpected probe {name}")

    monkeypatch.setattr(hd, "run_probe", fake_run_probe)
    monkeypatch.setattr(
        hd,
        "build_probe_registry",
        lambda _ctx: [
            ProbeSpec(name="host_resources", run=lambda _c: {}, applies=lambda _c: True),
            ProbeSpec(name="docker", run=lambda _c: {}, applies=lambda _c: True),
            ProbeSpec(name="nvidia_smi", run=lambda _c: {}, applies=lambda _c: False),
        ],
    )
    monkeypatch.setattr(hd, "reconcile_detected_fields", lambda _payload: ({}, {}, []))
    monkeypatch.setattr(
        hd,
        "FACT_REGISTRY",
        [
            ("arch", lambda _p: True),
            ("container_runtime", lambda _p: True),
            ("cpu_model", lambda _p: True),
        ],
    )

    out = hd.detect_server_hints().model_dump()
    assert calls[:3] == ["bootstrap_invariants", "execution_context", "os_router"]
    assert "host_resources" in calls
    assert "docker" in calls
    assert out["container_runtime"] == "runc"
    skipped = next(p for p in out["probes"] if p["name"] == "nvidia_smi")
    assert skipped["status"] == "warn"
    assert out["unknown_rate"] == 0.0


def test_unknown_rate_uses_fact_registry_predicates(monkeypatch):
    def fake_run_probe(name, _fn, context):
        if name == "bootstrap_invariants":
            return _probe_result(name, {"arch": "amd64", "os": "linux", "confidence": {"arch": "detected", "os": "detected"}})
        if name == "execution_context":
            return _probe_result(name, {"context": {}})
        if name == "os_router":
            context.os_branch = "generic_linux"
            return _probe_result(name, {})
        return _probe_result(name, {"confidence": {}})

    monkeypatch.setattr(hd, "run_probe", fake_run_probe)
    monkeypatch.setattr(hd, "build_probe_registry", lambda _ctx: [])
    monkeypatch.setattr(hd, "reconcile_detected_fields", lambda _payload: ({}, {}, []))
    monkeypatch.setattr(
        hd,
        "FACT_REGISTRY",
        [
            ("arch", lambda _p: True),
            ("gpu_vendor", lambda p: bool(p.get("gpu"))),
        ],
    )

    out = hd.detect_server_hints().model_dump()
    assert out["unknown_rate"] == 0.0


def test_route_os_branch():
    assert route_os_branch(ProbeContext(os="linux", os_family="ubuntu")) == "debian_ubuntu"
    assert route_os_branch(ProbeContext(os="linux", os_family="rhel")) == "generic_linux"
    assert route_os_branch(ProbeContext(os="darwin", os_family="macos")) == "unsupported"

