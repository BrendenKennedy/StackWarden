"""Hardware catalog schema, reconciliation, and YAML persistence."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from stackwarden.config import hardware_catalog_path
from stackwarden.web.util.write_yaml import atomic_write_yaml

MatchedBy = Literal["exact", "alias", "inferred"]


class HardwareCatalogItem(BaseModel):
    id: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    deprecated: bool = False

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        value = v.strip().lower()
        if not value:
            raise ValueError("id must not be empty")
        return value


class HardwareCatalog(BaseModel):
    schema_version: int = 1
    revision: int = 1
    arch: list[HardwareCatalogItem] = Field(default_factory=list)
    os_family: list[HardwareCatalogItem] = Field(default_factory=list)
    os_version: list[HardwareCatalogItem] = Field(default_factory=list)
    container_runtime: list[HardwareCatalogItem] = Field(default_factory=list)
    gpu_vendor: list[HardwareCatalogItem] = Field(default_factory=list)
    gpu_family: list[HardwareCatalogItem] = Field(default_factory=list)
    gpu_model: list[HardwareCatalogItem] = Field(default_factory=list)

    def items(self, key: str) -> list[HardwareCatalogItem]:
        return list(getattr(self, key, []))

    def resolve(self, key: str, raw: str | None) -> tuple[str | None, MatchedBy | None]:
        if not raw:
            return None, None
        needle = raw.strip().lower()
        if not needle:
            return None, None
        for item in self.items(key):
            if needle == item.id or needle == item.label.strip().lower():
                return item.id, "exact"
        for item in self.items(key):
            aliases = {a.strip().lower() for a in item.aliases}
            if needle in aliases:
                return item.id, "alias"
        if key == "gpu_model":
            tokenized = re.sub(r"[^a-z0-9]+", " ", needle).strip()
            for item in self.items(key):
                candidates = [item.id, item.label, *item.aliases]
                for candidate in candidates:
                    cand = re.sub(r"[^a-z0-9]+", " ", str(candidate).strip().lower()).strip()
                    if not cand:
                        continue
                    if re.search(rf"\b{re.escape(cand)}\b", tokenized):
                        return item.id, "inferred"
        return None, None


class CatalogSuggestion(BaseModel):
    catalog: str
    raw_value: str
    suggested_id: str


def default_hardware_catalog() -> HardwareCatalog:
    return HardwareCatalog(
        schema_version=1,
        revision=1,
        arch=[
            HardwareCatalogItem(id="amd64", label="AMD64", aliases=["x86_64"]),
            HardwareCatalogItem(id="arm64", label="ARM64", aliases=["aarch64"]),
            HardwareCatalogItem(id="ppc64le", label="PPC64LE", aliases=["powerpc64le"]),
        ],
        os_family=[
            HardwareCatalogItem(id="linux", label="Linux"),
            HardwareCatalogItem(id="ubuntu", label="Ubuntu"),
            HardwareCatalogItem(id="debian", label="Debian"),
            HardwareCatalogItem(id="rhel", label="RHEL"),
            HardwareCatalogItem(id="rocky", label="Rocky Linux"),
            HardwareCatalogItem(id="almalinux", label="AlmaLinux"),
            HardwareCatalogItem(id="centos", label="CentOS"),
            HardwareCatalogItem(id="sles", label="SUSE Linux Enterprise"),
            HardwareCatalogItem(id="opensuse", label="openSUSE"),
            HardwareCatalogItem(id="amazonlinux", label="Amazon Linux"),
            HardwareCatalogItem(id="fedora", label="Fedora"),
        ],
        os_version=[
            HardwareCatalogItem(id="linux_generic", label="Generic Linux", aliases=["linux"], parent_id="linux"),
            HardwareCatalogItem(id="ubuntu_20_04", label="Ubuntu 20.04", aliases=["20.04"], parent_id="ubuntu"),
            HardwareCatalogItem(id="ubuntu_22_04", label="Ubuntu 22.04", aliases=["22.04"], parent_id="ubuntu"),
            HardwareCatalogItem(id="ubuntu_24_04", label="Ubuntu 24.04", aliases=["24.04"], parent_id="ubuntu"),
            HardwareCatalogItem(
                id="ubuntu_24_10", label="Ubuntu 24.10", aliases=["24.10", "oracular"], parent_id="ubuntu"
            ),
            HardwareCatalogItem(id="debian_11", label="Debian 11", aliases=["11", "bullseye"], parent_id="debian"),
            HardwareCatalogItem(id="debian_12", label="Debian 12", aliases=["12", "bookworm"], parent_id="debian"),
            HardwareCatalogItem(id="debian_13", label="Debian 13", aliases=["13", "trixie"], parent_id="debian"),
            HardwareCatalogItem(id="rhel_8", label="RHEL 8", aliases=["8", "rhel8", "redhat8"], parent_id="rhel"),
            HardwareCatalogItem(id="rhel_9", label="RHEL 9", aliases=["9", "rhel9", "redhat9"], parent_id="rhel"),
            HardwareCatalogItem(id="rocky_8", label="Rocky Linux 8", aliases=["rocky8"], parent_id="rocky"),
            HardwareCatalogItem(id="rocky_9", label="Rocky Linux 9", aliases=["rocky9"], parent_id="rocky"),
            HardwareCatalogItem(id="almalinux_8", label="AlmaLinux 8", aliases=["alma8"], parent_id="almalinux"),
            HardwareCatalogItem(id="almalinux_9", label="AlmaLinux 9", aliases=["alma9"], parent_id="almalinux"),
            HardwareCatalogItem(id="centos_7", label="CentOS 7", aliases=["centos7"], parent_id="centos"),
            HardwareCatalogItem(
                id="centos_stream_8", label="CentOS Stream 8", aliases=["centos8"], parent_id="centos"
            ),
            HardwareCatalogItem(
                id="centos_stream_9", label="CentOS Stream 9", aliases=["centos9"], parent_id="centos"
            ),
            HardwareCatalogItem(id="sles_15", label="SLES 15", aliases=["sles15"], parent_id="sles"),
            HardwareCatalogItem(
                id="opensuse_15_6", label="openSUSE Leap 15.6", aliases=["leap15.6"], parent_id="opensuse"
            ),
            HardwareCatalogItem(
                id="opensuse_tumbleweed",
                label="openSUSE Tumbleweed",
                aliases=["tumbleweed"],
                parent_id="opensuse",
            ),
            HardwareCatalogItem(id="amazonlinux_2", label="Amazon Linux 2", aliases=["amzn2"], parent_id="amazonlinux"),
            HardwareCatalogItem(
                id="amazonlinux_2023", label="Amazon Linux 2023", aliases=["amzn2023"], parent_id="amazonlinux"
            ),
            HardwareCatalogItem(id="fedora_39", label="Fedora 39", aliases=["f39"], parent_id="fedora"),
            HardwareCatalogItem(id="fedora_40", label="Fedora 40", aliases=["f40"], parent_id="fedora"),
            HardwareCatalogItem(id="fedora_41", label="Fedora 41", aliases=["f41"], parent_id="fedora"),
        ],
        container_runtime=[
            HardwareCatalogItem(id="nvidia", label="NVIDIA Runtime"),
            HardwareCatalogItem(id="runc", label="runc"),
        ],
        gpu_vendor=[
            HardwareCatalogItem(id="nvidia", label="NVIDIA"),
            HardwareCatalogItem(id="amd", label="AMD"),
            HardwareCatalogItem(id="intel", label="Intel"),
        ],
        gpu_family=[
            HardwareCatalogItem(id="blackwell", label="Blackwell", parent_id="nvidia"),
            HardwareCatalogItem(id="ada", label="Ada", parent_id="nvidia"),
            HardwareCatalogItem(id="hopper", label="Hopper", parent_id="nvidia"),
            HardwareCatalogItem(id="ampere", label="Ampere", parent_id="nvidia"),
            HardwareCatalogItem(id="turing", label="Turing", parent_id="nvidia"),
            HardwareCatalogItem(id="volta", label="Volta", parent_id="nvidia"),
            HardwareCatalogItem(id="pascal", label="Pascal", parent_id="nvidia"),
            HardwareCatalogItem(id="maxwell", label="Maxwell", parent_id="nvidia"),
            HardwareCatalogItem(id="cdna3", label="CDNA3", parent_id="amd"),
            HardwareCatalogItem(id="cdna2", label="CDNA2", parent_id="amd"),
            HardwareCatalogItem(id="cdna", label="CDNA", parent_id="amd"),
            HardwareCatalogItem(id="rdna3", label="RDNA3", parent_id="amd"),
            HardwareCatalogItem(id="rdna2", label="RDNA2", parent_id="amd"),
            HardwareCatalogItem(id="gcn", label="GCN", parent_id="amd"),
            HardwareCatalogItem(id="xehpc", label="Xe HPC", parent_id="intel"),
            HardwareCatalogItem(id="xehpg", label="Xe HPG", parent_id="intel"),
            HardwareCatalogItem(id="xelp", label="Xe LP", parent_id="intel"),
            HardwareCatalogItem(id="max", label="Data Center GPU Max", parent_id="intel"),
            HardwareCatalogItem(id="arc", label="Arc", parent_id="intel"),
            HardwareCatalogItem(id="flex", label="Data Center GPU Flex", parent_id="intel"),
        ],
        gpu_model=[
            HardwareCatalogItem(id="nvidia_gb10", label="NVIDIA GB10", aliases=["gb10", "nvidia gb10"], parent_id="blackwell"),
            HardwareCatalogItem(id="nvidia_b200", label="NVIDIA B200", aliases=["b200"], parent_id="blackwell"),
            HardwareCatalogItem(id="nvidia_b100", label="NVIDIA B100", aliases=["b100"], parent_id="blackwell"),
            HardwareCatalogItem(id="nvidia_h200", label="NVIDIA H200", aliases=["h200"], parent_id="hopper"),
            HardwareCatalogItem(
                id="nvidia_h100", label="NVIDIA H100", aliases=["h100", "sxm_h100", "pcie_h100"], parent_id="hopper"
            ),
            HardwareCatalogItem(id="nvidia_gh200", label="NVIDIA GH200", aliases=["gh200"], parent_id="hopper"),
            HardwareCatalogItem(id="nvidia_l40s", label="NVIDIA L40S", aliases=["l40s"], parent_id="ada"),
            HardwareCatalogItem(id="nvidia_l40", label="NVIDIA L40", aliases=["l40"], parent_id="ada"),
            HardwareCatalogItem(
                id="nvidia_rtx_6000_ada",
                label="NVIDIA RTX 6000 Ada",
                aliases=["rtx 6000 ada", "rtx6000_ada"],
                parent_id="ada",
            ),
            HardwareCatalogItem(id="nvidia_l4", label="NVIDIA L4", aliases=["l4"], parent_id="ada"),
            HardwareCatalogItem(
                id="nvidia_a100", label="NVIDIA A100", aliases=["a100", "sxm_a100", "pcie_a100"], parent_id="ampere"
            ),
            HardwareCatalogItem(id="nvidia_a30", label="NVIDIA A30", aliases=["a30"], parent_id="ampere"),
            HardwareCatalogItem(id="nvidia_a10", label="NVIDIA A10", aliases=["a10"], parent_id="ampere"),
            HardwareCatalogItem(id="nvidia_a10g", label="NVIDIA A10G", aliases=["a10g"], parent_id="ampere"),
            HardwareCatalogItem(id="nvidia_a16", label="NVIDIA A16", aliases=["a16"], parent_id="ampere"),
            HardwareCatalogItem(id="nvidia_rtx_a6000", label="NVIDIA RTX A6000", aliases=["rtx a6000"], parent_id="ampere"),
            HardwareCatalogItem(
                id="nvidia_rtx_3090", label="NVIDIA RTX 3090", aliases=["rtx 3090", "3090"], parent_id="ampere"
            ),
            HardwareCatalogItem(
                id="nvidia_rtx_3080", label="NVIDIA RTX 3080", aliases=["rtx 3080", "3080"], parent_id="ampere"
            ),
            HardwareCatalogItem(id="nvidia_t4", label="NVIDIA T4", aliases=["t4", "tesla_t4"], parent_id="turing"),
            HardwareCatalogItem(
                id="nvidia_rtx_2080_ti",
                label="NVIDIA RTX 2080 Ti",
                aliases=["rtx 2080 ti", "2080ti"],
                parent_id="turing",
            ),
            HardwareCatalogItem(id="nvidia_v100", label="NVIDIA V100", aliases=["v100", "tesla_v100"], parent_id="volta"),
            HardwareCatalogItem(id="nvidia_titan_v", label="NVIDIA TITAN V", aliases=["titan v"], parent_id="volta"),
            HardwareCatalogItem(id="nvidia_p100", label="NVIDIA P100", aliases=["p100", "tesla_p100"], parent_id="pascal"),
            HardwareCatalogItem(id="nvidia_p40", label="NVIDIA P40", aliases=["p40", "tesla_p40"], parent_id="pascal"),
            HardwareCatalogItem(id="nvidia_m60", label="NVIDIA M60", aliases=["m60", "tesla_m60"], parent_id="maxwell"),
            HardwareCatalogItem(id="amd_mi325x", label="AMD Instinct MI325X", aliases=["mi325x"], parent_id="cdna3"),
            HardwareCatalogItem(id="amd_mi300x", label="AMD Instinct MI300X", aliases=["mi300x"], parent_id="cdna3"),
            HardwareCatalogItem(id="amd_mi300a", label="AMD Instinct MI300A", aliases=["mi300a"], parent_id="cdna3"),
            HardwareCatalogItem(id="amd_mi250x", label="AMD Instinct MI250X", aliases=["mi250x"], parent_id="cdna2"),
            HardwareCatalogItem(id="amd_mi210", label="AMD Instinct MI210", aliases=["mi210"], parent_id="cdna2"),
            HardwareCatalogItem(id="amd_mi100", label="AMD Instinct MI100", aliases=["mi100"], parent_id="cdna"),
            HardwareCatalogItem(id="amd_w7900", label="AMD Radeon PRO W7900", aliases=["w7900"], parent_id="rdna3"),
            HardwareCatalogItem(id="amd_w7800", label="AMD Radeon PRO W7800", aliases=["w7800"], parent_id="rdna3"),
            HardwareCatalogItem(
                id="amd_rx_7900_xtx",
                label="AMD Radeon RX 7900 XTX",
                aliases=["rx 7900 xtx", "7900xtx"],
                parent_id="rdna3",
            ),
            HardwareCatalogItem(
                id="amd_rx_6800_xt",
                label="AMD Radeon RX 6800 XT",
                aliases=["rx 6800 xt", "6800xt"],
                parent_id="rdna2",
            ),
            HardwareCatalogItem(id="amd_v520", label="AMD Radeon Pro V520", aliases=["v520"], parent_id="gcn"),
            HardwareCatalogItem(
                id="intel_max_1550",
                label="Intel Data Center GPU Max 1550",
                aliases=["max 1550"],
                parent_id="max",
            ),
            HardwareCatalogItem(
                id="intel_max_1100",
                label="Intel Data Center GPU Max 1100",
                aliases=["max 1100"],
                parent_id="max",
            ),
            HardwareCatalogItem(
                id="intel_flex_170",
                label="Intel Data Center GPU Flex 170",
                aliases=["flex 170"],
                parent_id="flex",
            ),
            HardwareCatalogItem(
                id="intel_flex_140",
                label="Intel Data Center GPU Flex 140",
                aliases=["flex 140"],
                parent_id="flex",
            ),
            HardwareCatalogItem(id="intel_arc_a770", label="Intel Arc A770", aliases=["arc a770", "a770"], parent_id="arc"),
            HardwareCatalogItem(id="intel_arc_a750", label="Intel Arc A750", aliases=["arc a750", "a750"], parent_id="arc"),
        ],
    )


def load_hardware_catalog(path: Path | None = None) -> HardwareCatalog:
    target = path or hardware_catalog_path()
    if not target.exists():
        return default_hardware_catalog()
    with open(target, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return HardwareCatalog.model_validate(raw)


def save_hardware_catalog(
    catalog: HardwareCatalog,
    *,
    path: Path | None = None,
    expected_revision: int | None = None,
) -> HardwareCatalog:
    current = load_hardware_catalog(path)
    if expected_revision is not None and current.revision != expected_revision:
        raise ValueError(
            f"Catalog revision mismatch: expected {expected_revision}, found {current.revision}"
        )
    updated = catalog.model_copy(update={"revision": current.revision + 1})
    target = path or hardware_catalog_path()
    atomic_write_yaml(updated.model_dump(mode="json"), target)
    return updated


def reconcile_detected_fields(payload: dict) -> tuple[dict[str, str], dict[str, MatchedBy], list[dict[str, str]]]:
    """Map detection values to catalog IDs and return unresolved suggestions."""
    catalog = load_hardware_catalog()
    resolved: dict[str, str] = {}
    matched_by: dict[str, MatchedBy] = {}
    unmatched: list[dict[str, str]] = []
    gpu_obj = payload.get("gpu")

    def _gpu_attr(name: str) -> str | None:
        if isinstance(gpu_obj, dict):
            value = gpu_obj.get(name)
            return str(value) if value is not None else None
        if gpu_obj is not None and hasattr(gpu_obj, name):
            value = getattr(gpu_obj, name)
            return str(value) if value is not None else None
        return None

    fields = [
        ("arch", payload.get("arch")),
        ("os_family", payload.get("os_family")),
        ("os_version", payload.get("os_version")),
        ("container_runtime", payload.get("container_runtime")),
        ("gpu_vendor", _gpu_attr("vendor")),
        ("gpu_family", _gpu_attr("family")),
        ("gpu_model", payload.get("gpu_model")),
    ]
    for key, value in fields:
        rid, matched = catalog.resolve(key, value)
        if rid:
            resolved[f"{key}_id"] = rid
            if matched:
                matched_by[f"{key}_id"] = matched
        elif value:
            token = str(value).strip().lower().replace(" ", "_")
            unmatched.append({"catalog": key, "raw_value": str(value), "suggested_id": token})
    return resolved, matched_by, unmatched

