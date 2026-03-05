"""Probe primitives and helpers for server-host detection."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from stacksmith.runtime.docker_client import DockerClient
from stacksmith.web.schemas import DetectionProbeDTO

_CUDA_TOKEN_RE = re.compile(r"CUDA Version:\s*(\d+)\.(\d+)")

QualityPredicate = Callable[[dict], bool]


@dataclass
class ProbeResult:
    probe: DetectionProbeDTO
    payload: dict


@dataclass
class ProbeContext:
    arch: str | None = None
    os: str | None = None
    os_family: str | None = None
    os_version: str | None = None
    os_branch: str = "unknown"
    docker_available: bool = False
    docker_socket_present: bool = False
    nvidia_smi_available: bool = False
    in_container: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ProbeSpec:
    name: str
    run: Callable[[ProbeContext], dict]
    applies: Callable[[ProbeContext], bool] = lambda _ctx: True


FACT_REGISTRY: list[tuple[str, QualityPredicate]] = [
    ("arch", lambda _p: True),
    ("os", lambda _p: True),
    ("os_family", lambda p: (p.get("os") or "").lower() == "linux"),
    ("os_version", lambda p: (p.get("os") or "").lower() == "linux"),
    ("container_runtime", lambda _p: True),
    ("cpu_model", lambda _p: True),
    ("cpu_cores_logical", lambda _p: True),
    ("cpu_cores_physical", lambda _p: True),
    ("memory_gb_total", lambda _p: True),
    ("disk_gb_total", lambda _p: True),
    ("gpu_vendor", lambda p: bool(p.get("gpu") or p.get("cuda_available"))),
    ("gpu_family", lambda p: bool(p.get("gpu") or p.get("cuda_available"))),
    ("gpu_model", lambda p: bool(p.get("gpu") or p.get("cuda_available"))),
    ("driver_version", lambda p: bool(p.get("gpu") or p.get("cuda_available"))),
    ("compute_capability", lambda p: bool(p.get("gpu") or p.get("cuda_available"))),
    ("cuda_runtime", lambda p: bool(p.get("gpu") or p.get("cuda_available"))),
]


def run_probe(name: str, fn: Callable[[ProbeContext], dict], context: ProbeContext) -> ProbeResult:
    started = time.monotonic()
    try:
        payload = fn(context) or {}
        elapsed = int((time.monotonic() - started) * 1000)
        msg = payload.pop("_message", "")
        return ProbeResult(
            probe=DetectionProbeDTO(name=name, status="ok", message=msg, duration_ms=elapsed),
            payload=payload,
        )
    except Exception as exc:  # pragma: no cover - defensive
        elapsed = int((time.monotonic() - started) * 1000)
        return ProbeResult(
            probe=DetectionProbeDTO(name=name, status="warn", message=str(exc), duration_ms=elapsed),
            payload={},
        )


def merge_payload(base: dict, incoming: dict) -> None:
    """Merge probe payloads while avoiding destructive overwrites."""
    for key, val in incoming.items():
        if key == "capabilities_suggested":
            existing = set(base.get("capabilities_suggested", []))
            existing.update(val or [])
            base["capabilities_suggested"] = sorted(existing)
            continue
        if key == "confidence":
            conf = base.get("confidence", {})
            conf.update(val or {})
            base["confidence"] = conf
            continue
        if val is None:
            continue
        if key not in base or base.get(key) in (None, "", [], {}):
            base[key] = val
            continue
        if key in {"driver_version", "supported_cuda_min", "supported_cuda_max", "gpu_devices"}:
            base[key] = val


def init_context() -> ProbeContext:
    return ProbeContext()


def update_context_from_payload(context: ProbeContext, payload: dict) -> None:
    context.arch = payload.get("arch") or context.arch
    context.os = payload.get("os") or context.os
    context.os_family = payload.get("os_family") or context.os_family
    context.os_version = payload.get("os_version") or context.os_version


def route_os_branch(context: ProbeContext) -> str:
    if (context.os or "").lower() != "linux":
        return "unsupported"
    fam = (context.os_family or "").lower()
    if fam in {"ubuntu", "debian"}:
        return "debian_ubuntu"
    return "generic_linux"


def build_probe_registry(context: ProbeContext) -> list[ProbeSpec]:
    return [
        ProbeSpec(name="host_resources", run=probe_host_resources, applies=lambda c: c.os_branch != "unsupported"),
        ProbeSpec(name="docker", run=probe_docker, applies=lambda c: c.docker_available or c.docker_socket_present),
        ProbeSpec(name="nvidia_smi", run=probe_nvidia_smi, applies=lambda c: c.nvidia_smi_available),
    ]


def probe_bootstrap_invariants(_context: ProbeContext) -> dict:
    machine = platform.machine().lower()
    arch_map = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    os_family, os_version = read_os_release()
    os_name = platform.system().lower()
    return {
        "arch": arch_map.get(machine, machine),
        "os": os_name,
        "os_family": os_family.lower() if os_family else None,
        "os_version": os_version,
        "confidence": {
            "arch": "detected",
            "os": "detected",
            "os_family": "detected" if os_family else "unknown",
            "os_version": "detected" if os_version else "unknown",
        },
        "_message": f"{platform.system()} / {machine}",
    }


def probe_execution_context(_context: ProbeContext) -> dict:
    docker_socket = Path("/var/run/docker.sock").exists()
    docker_bin = shutil.which("docker") is not None
    nvidia_bin = shutil.which("nvidia-smi") is not None
    in_container = Path("/.dockerenv").exists() or cgroup_contains_container_tokens()
    return {
        "context": {
            "docker_socket_present": docker_socket,
            "docker_available": docker_bin or docker_socket,
            "nvidia_smi_available": nvidia_bin,
            "in_container": in_container,
        },
        "_message": f"docker={'yes' if (docker_bin or docker_socket) else 'no'} nvidia_smi={'yes' if nvidia_bin else 'no'}",
    }


def probe_os_router(context: ProbeContext) -> dict:
    context.os_branch = route_os_branch(context)
    return {"_message": f"branch={context.os_branch}"}


def probe_host_resources(context: ProbeContext) -> dict:
    if context.os_branch == "debian_ubuntu":
        cpu_model, logical_cores, physical_cores = read_cpu_info_debian()
        memory_gb_total = read_mem_total_gb_debian()
    else:
        cpu_model, logical_cores, physical_cores = read_cpu_info_generic_linux()
        memory_gb_total = read_mem_total_gb_generic_linux()
    disk_gb_total = read_disk_total_gb()
    confidence = {
        "cpu_model": "detected" if cpu_model else "unknown",
        "cpu_cores_logical": "detected" if logical_cores is not None else "unknown",
        "cpu_cores_physical": "detected" if physical_cores is not None else "unknown",
        "memory_gb_total": "detected" if memory_gb_total is not None else "unknown",
        "disk_gb_total": "detected" if disk_gb_total is not None else "unknown",
    }
    return {
        "cpu_model": cpu_model,
        "cpu_cores_logical": logical_cores,
        "cpu_cores_physical": physical_cores,
        "memory_gb_total": memory_gb_total,
        "disk_gb_total": disk_gb_total,
        "confidence": confidence,
        "_message": (
            f"os_branch={context.os_branch} cpu={logical_cores or 'unknown'} "
            f"mem={memory_gb_total or 'unknown'}GB"
        ),
    }


def probe_docker(_context: ProbeContext) -> dict:
    docker = DockerClient()
    info = docker.info()
    runtime_names = set((info.get("Runtimes") or {}).keys())
    runtime = "nvidia" if "nvidia" in runtime_names else "runc"
    arch = str(info.get("Architecture", "")).lower() or None
    os_type = str(info.get("OSType", "")).lower() or None
    arch_map = {"x86_64": "amd64", "aarch64": "arm64"}
    return {
        "arch": arch_map.get(arch, arch),
        "os": os_type,
        "container_runtime": runtime,
        "confidence": {
            "container_runtime": "detected",
        },
        "_message": f"daemon={os_type or 'unknown'}/{arch or 'unknown'}",
    }


def probe_nvidia_smi(_context: ProbeContext) -> dict:
    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=3)
    if result.returncode != 0:
        raise RuntimeError("nvidia-smi returned non-zero")
    out = result.stdout

    cuda_major = 0
    cuda_minor = 0
    m = _CUDA_TOKEN_RE.search(out)
    if m:
        cuda_major = int(m.group(1))
        cuda_minor = int(m.group(2))

    names = query_csv("nvidia-smi", "name")
    family = infer_gpu_family(names[0] if names else "")
    cc_vals = query_csv("nvidia-smi", "compute_cap")
    mem_vals = query_csv("nvidia-smi", "memory.total", nounits=True)
    driver_vals = query_csv("nvidia-smi", "driver_version")
    driver = driver_vals[0] if driver_vals else None

    payload: dict = {
        "cuda_available": True,
        "capabilities_suggested": ["cuda"],
        "gpu_model": names[0] if names else None,
        "gpu": {
            "vendor": "nvidia",
            "family": family,
            "compute_capability": cc_vals[0] if cc_vals else None,
        },
        "gpu_devices": [
            {
                "index": i,
                "model": names[i] if i < len(names) else None,
                "family": infer_gpu_family(names[i]) if i < len(names) else family,
                "compute_capability": cc_vals[i] if i < len(cc_vals) else None,
                "memory_gb": parse_mib_to_gib(mem_vals[i] if i < len(mem_vals) else None),
            }
            for i in range(max(len(names), len(cc_vals), len(mem_vals), 1))
        ],
        "confidence": {
            "gpu_vendor": "detected",
            "gpu_family": "inferred",
            "gpu_model": "detected" if names else "unknown",
            "driver_version": "detected" if driver else "unknown",
            "compute_capability": "detected" if cc_vals else "unknown",
            "cuda_runtime": "detected" if cuda_major > 0 else "unknown",
        },
    }
    if cuda_major > 0:
        payload["cuda"] = {
            "major": cuda_major,
            "minor": cuda_minor,
            "variant": f"cuda{cuda_major}.{cuda_minor}",
        }
        payload["supported_cuda_min"] = f"{cuda_major}.0"
        payload["supported_cuda_max"] = f"{cuda_major}.{cuda_minor}"
    if driver:
        payload["driver_version"] = driver
    if names:
        payload["_message"] = ", ".join(names)
    return payload


def parse_mib_to_gib(raw: str | None) -> float | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    lowered = token.lower()
    if lowered in {"[n/a]", "n/a", "na", "none", "null"}:
        return None
    try:
        return float(token) / 1024.0
    except ValueError:
        return None


def query_csv(binary: str, field: str, nounits: bool = False) -> list[str]:
    fmt = "csv,noheader,nounits" if nounits else "csv,noheader"
    q = subprocess.run(
        [binary, f"--query-gpu={field}", f"--format={fmt}"],
        capture_output=True,
        text=True,
        timeout=3,
    )
    if q.returncode != 0:
        return []
    return [line.strip() for line in q.stdout.splitlines() if line.strip()]


def infer_gpu_family(name: str) -> str:
    n = name.lower()
    if (
        "blackwell" in n
        or "gb10" in n
        or "b200" in n
        or "b100" in n
        or "rtx 50" in n
        or "rtx50" in n
    ):
        return "blackwell"
    if "h100" in n or "hopper" in n or "h200" in n:
        return "hopper"
    if "ada" in n or "rtx 6000 ada" in n or "l40" in n or "l4" in n:
        return "ada"
    if "a100" in n or "ampere" in n or "rtx 30" in n or "rtx 40" in n:
        return "ampere"
    if "t4" in n or "turing" in n:
        return "turing"
    if "v100" in n or "volta" in n:
        return "volta"
    return "gpu"


def read_os_release() -> tuple[str | None, str | None]:
    for candidate in (Path("/etc/os-release"), Path("/usr/lib/os-release")):
        if not candidate.exists():
            continue
        try:
            lines: dict[str, str] = {}
            with candidate.open(encoding="utf-8") as f:
                for raw in f:
                    if "=" not in raw:
                        continue
                    k, v = raw.strip().split("=", 1)
                    lines[k] = v.strip('"')
            return lines.get("ID"), lines.get("VERSION_ID")
        except OSError:
            continue
    return None, None


def read_cpu_info_debian() -> tuple[str | None, int | None, int | None]:
    model, logical, physical = read_cpu_info_proc()
    if model and logical is not None:
        return model, logical, physical
    lscpu = read_cpu_info_lscpu()
    return lscpu if lscpu[0] or lscpu[1] is not None else (model, logical, physical)


def read_cpu_info_generic_linux() -> tuple[str | None, int | None, int | None]:
    model, logical, physical = read_cpu_info_lscpu()
    if model or logical is not None:
        return model, logical, physical
    return read_cpu_info_proc()


def read_cpu_info_proc() -> tuple[str | None, int | None, int | None]:
    model: str | None = None
    physical_core_pairs: set[tuple[int, int]] = set()
    seen_physical_tokens = False
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        try:
            physical_id: int | None = None
            core_id: int | None = None
            with cpuinfo.open(encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        if physical_id is not None and core_id is not None:
                            physical_core_pairs.add((physical_id, core_id))
                        physical_id = None
                        core_id = None
                        continue
                    if ":" not in line:
                        continue
                    key, value = [token.strip() for token in line.split(":", 1)]
                    lower_key = key.lower()
                    if lower_key == "model name" and not model:
                        model = value
                    elif lower_key == "physical id":
                        seen_physical_tokens = True
                        try:
                            physical_id = int(value)
                        except ValueError:
                            physical_id = None
                    elif lower_key == "core id":
                        seen_physical_tokens = True
                        try:
                            core_id = int(value)
                        except ValueError:
                            core_id = None
            if physical_id is not None and core_id is not None:
                physical_core_pairs.add((physical_id, core_id))
        except OSError:
            pass
    logical = cpu_count()
    physical = len(physical_core_pairs) if seen_physical_tokens and physical_core_pairs else None
    return model, logical, physical


def read_cpu_info_lscpu() -> tuple[str | None, int | None, int | None]:
    if shutil.which("lscpu") is None:
        return None, None, None
    try:
        res = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None, None, None
    if res.returncode != 0:
        return None, None, None
    model = None
    logical = None
    physical = None
    for line in res.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = [token.strip() for token in line.split(":", 1)]
        if key == "Model name" and not model:
            model = value
        elif key == "CPU(s)" and logical is None:
            try:
                logical = int(value)
            except ValueError:
                pass
        elif key == "Core(s) per socket":
            try:
                per_socket = int(value)
                sockets = 1
                sock_line = next((s for s in res.stdout.splitlines() if s.startswith("Socket(s):")), None)
                if sock_line and ":" in sock_line:
                    try:
                        sockets = int(sock_line.split(":", 1)[1].strip())
                    except ValueError:
                        sockets = 1
                physical = per_socket * sockets
            except ValueError:
                pass
    return model, logical, physical


def cpu_count() -> int | None:
    count = None
    try:
        count = os.cpu_count()
    except Exception:
        count = None
    return count if isinstance(count, int) and count > 0 else None


def read_mem_total_gb_debian() -> float | None:
    mem = read_mem_total_gb_proc()
    if mem is not None:
        return mem
    return read_mem_total_gb_sysconf()


def read_mem_total_gb_generic_linux() -> float | None:
    mem = read_mem_total_gb_sysconf()
    if mem is not None:
        return mem
    return read_mem_total_gb_proc()


def read_mem_total_gb_proc() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    try:
        with meminfo.open(encoding="utf-8") as f:
            for raw in f:
                if raw.startswith("MemTotal:"):
                    parts = raw.split()
                    if len(parts) >= 2:
                        kb = float(parts[1])
                        return round(kb / (1024.0 * 1024.0), 2)
    except (OSError, ValueError):
        return None
    return None


def read_mem_total_gb_sysconf() -> float | None:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        if page_size <= 0 or pages <= 0:
            return None
        total = float(page_size * pages)
        return round(total / (1024.0 * 1024.0 * 1024.0), 2)
    except (ValueError, OSError, AttributeError):
        return None


def read_disk_total_gb() -> float | None:
    primary = read_disk_total_gb_shutil()
    if primary is not None:
        return primary
    return read_disk_total_gb_df()


def read_disk_total_gb_shutil() -> float | None:
    try:
        total = shutil.disk_usage("/").total
        return round(total / (1024.0 * 1024.0 * 1024.0), 2)
    except OSError:
        return None


def read_disk_total_gb_df() -> float | None:
    if shutil.which("df") is None:
        return None
    try:
        res = subprocess.run(["df", "-k", "/"], capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    parts = lines[-1].split()
    if len(parts) < 2:
        return None
    try:
        kb = float(parts[1])
    except ValueError:
        return None
    return round(kb / (1024.0 * 1024.0), 2)


def cgroup_contains_container_tokens() -> bool:
    cg = Path("/proc/1/cgroup")
    if not cg.exists():
        return False
    try:
        raw = cg.read_text(encoding="utf-8")
    except OSError:
        return False
    lowered = raw.lower()
    return any(token in lowered for token in ("docker", "kubepods", "containerd"))

