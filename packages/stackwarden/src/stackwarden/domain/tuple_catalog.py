"""Architecture-aware tuple catalog models and loading."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from stackwarden.config import tuple_catalog_roots


TupleStatus = Literal["supported", "experimental", "unsupported"]


class TupleSelector(BaseModel):
    arch: str
    os_family_id: str
    os_version_id: str
    container_runtime: str
    gpu_vendor_id: str
    gpu_family_id: str | None = None
    cuda_min: float | None = None
    cuda_max: float | None = None
    driver_min: float | None = None


class SupportedTuple(BaseModel):
    id: str
    status: TupleStatus = "supported"
    selector: TupleSelector
    base_image: str = ""
    wheelhouse_path: str = ""
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class TupleCatalog(BaseModel):
    schema_version: int = 1
    revision: int = 1
    tuples: list[SupportedTuple] = Field(default_factory=list)


def default_tuple_catalog() -> TupleCatalog:
    return TupleCatalog(
        schema_version=1,
        revision=1,
        tuples=[
            SupportedTuple(
                id="x86_nvidia_cuda124_ubuntu2204",
                status="supported",
                selector=TupleSelector(
                    arch="amd64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_22_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    cuda_min=12.4,
                    cuda_max=12.4,
                ),
                base_image="nvcr.io/nvidia/pytorch:24.06-py3",
                notes="Reference x86 CUDA 12.4 path.",
                tags=["golden", "x86", "cuda12.4"],
            ),
            SupportedTuple(
                id="x86_nvidia_cuda125_ubuntu2204",
                status="supported",
                selector=TupleSelector(
                    arch="amd64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_22_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    cuda_min=12.5,
                    cuda_max=12.5,
                ),
                base_image="nvcr.io/nvidia/pytorch:24.08-py3",
                notes="Generic x86 CUDA 12.5 path.",
                tags=["golden", "x86", "cuda12.5", "generic"],
            ),
            SupportedTuple(
                id="dgx_h100_cuda125_ubuntu2204",
                status="supported",
                selector=TupleSelector(
                    arch="amd64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_22_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    gpu_family_id="hopper",
                    cuda_min=12.5,
                    cuda_max=12.5,
                ),
                base_image="nvcr.io/nvidia/pytorch:24.08-py3",
                notes="Authoritative DGX H100 baseline on Ubuntu 22.04 (Hopper, CUDA 12.5).",
                tags=["golden", "dgx", "dgx-h100", "hopper", "cuda12.5", "authoritative"],
            ),
            SupportedTuple(
                id="arm_nvidia_cuda124_ubuntu2204",
                status="experimental",
                selector=TupleSelector(
                    arch="arm64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_22_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    cuda_min=12.4,
                    cuda_max=12.5,
                ),
                base_image="nvcr.io/nvidia/pytorch:24.06-py3",
                notes="ARM path may require wheelhouse for some packages.",
                tags=["golden", "arm", "requires_wheelhouse"],
            ),
            SupportedTuple(
                id="arm_nvidia_cuda124_ubuntu2404",
                status="experimental",
                selector=TupleSelector(
                    arch="arm64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_24_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    cuda_min=12.4,
                    cuda_max=12.5,
                ),
                base_image="nvcr.io/nvidia/pytorch:24.10-py3",
                notes="ARM Ubuntu 24.04 (e.g. DGX Spark). May require wheelhouse for some packages.",
                tags=["golden", "arm", "ubuntu24", "requires_wheelhouse"],
            ),
            SupportedTuple(
                id="arm_nvidia_cuda130_ubuntu2404",
                status="supported",
                selector=TupleSelector(
                    arch="arm64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_24_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    gpu_family_id="blackwell",
                    cuda_min=13.0,
                    cuda_max=13.0,
                ),
                base_image="nvcr.io/nvidia/pytorch:25.03-py3",
                notes="DGX Spark Blackwell GB10 primary path on arm64 Ubuntu 24.04.",
                tags=["golden", "arm", "cuda13.0", "blackwell", "dgx-spark", "authoritative"],
            ),
            SupportedTuple(
                id="arm_nvidia_cuda130_ubuntu2404_pull",
                status="supported",
                selector=TupleSelector(
                    arch="arm64",
                    os_family_id="ubuntu",
                    os_version_id="ubuntu_24_04",
                    container_runtime="nvidia",
                    gpu_vendor_id="nvidia",
                    gpu_family_id="blackwell",
                    cuda_min=13.0,
                    cuda_max=13.0,
                ),
                base_image="nvcr.io/nvidia/pytorch:25.03-py3",
                notes="DGX Spark pull-focused path for prebuilt image flows.",
                tags=["golden", "arm", "cuda13.0", "blackwell", "dgx-spark", "pull", "authoritative"],
            ),
            SupportedTuple(
                id="cpu_amd64_runc_linux",
                status="supported",
                selector=TupleSelector(
                    arch="amd64",
                    os_family_id="linux",
                    os_version_id="linux_generic",
                    container_runtime="runc",
                    gpu_vendor_id="cpu",
                ),
                base_image="python:3.11-slim",
                notes="CPU fallback for non-GPU stacks.",
                tags=["cpu", "fallback"],
            ),
            SupportedTuple(
                id="arm_cpu_runc_linux",
                status="experimental",
                selector=TupleSelector(
                    arch="arm64",
                    os_family_id="linux",
                    os_version_id="linux_generic",
                    container_runtime="runc",
                    gpu_vendor_id="cpu",
                ),
                base_image="python:3.11-slim",
                notes="ARM CPU fallback for utility workloads.",
                tags=["cpu", "arm", "fallback"],
            ),
        ],
    )


def load_tuple_catalog(path: Path | None = None) -> TupleCatalog:
    """Load tuple catalog, merging from all roots (bundled, remote, local) so remote complements local."""
    if path is not None:
        if not path.exists():
            return default_tuple_catalog()
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return TupleCatalog.model_validate(raw)

    merged: dict[str, SupportedTuple] = {}
    for t in default_tuple_catalog().tuples:
        merged[t.id] = t

    for root in tuple_catalog_roots():
        target = root / "tuple_catalog.yaml"
        if not target.exists():
            continue
        with open(target, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        catalog = TupleCatalog.model_validate(raw)
        for t in catalog.tuples:
            merged[t.id] = t

    return TupleCatalog(
        schema_version=1,
        revision=1,
        tuples=list(merged.values()),
    )
