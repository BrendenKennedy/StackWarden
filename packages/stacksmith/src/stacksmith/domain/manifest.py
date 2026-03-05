"""Resolved manifest schema — post-build lockfile capturing exact installed versions."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from stacksmith.domain.snapshots import artifact_dir


class ResolvedManifest(BaseModel):
    profile_id: str
    stack_id: str
    fingerprint: str
    base_image: str
    base_digest: str | None = None
    python_version: str = ""
    pip_freeze: list[str] = Field(default_factory=list)
    pip_install_mode: str = "index"
    pip_wheelhouse_path: str = ""
    npm_install_mode: str = "spec"
    apt_install_mode: str = "repo"
    tuple_id: str = ""
    tuple_status: str = ""
    tuple_mode: str = ""
    apt_packages: list[str] = Field(default_factory=list)
    npm_packages: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)
    entrypoint: list[str] = Field(default_factory=list)
    variant_overrides: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""


def manifest_dir(fingerprint: str) -> Path:
    return artifact_dir(fingerprint)


def save_manifest(manifest: ResolvedManifest) -> Path:
    d = manifest_dir(manifest.fingerprint)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2))
    return path


def load_manifest(fingerprint: str) -> ResolvedManifest:
    path = manifest_dir(fingerprint) / "manifest.json"
    return ResolvedManifest.model_validate_json(path.read_text())
