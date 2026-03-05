"""Remote catalog sync helpers (clone/pull) for StackWarden data repos."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from stackwarden.config import AppConfig


@dataclass
class RemoteCatalogSyncResult:
    status: str
    detail: str
    commit: str | None = None
    local_path: str | None = None


def _git_timeout_seconds() -> int:
    raw = os.environ.get("STACKWARDEN_REMOTE_GIT_TIMEOUT", "").strip()
    if not raw:
        return 30
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    timeout = _git_timeout_seconds()
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git {' '.join(args)} timed out after {timeout}s"
        ) from exc
    return completed.stdout.strip()


def sync_remote_catalog(cfg: AppConfig) -> RemoteCatalogSyncResult:
    """Clone or pull the configured remote catalog repository."""
    if not cfg.remote_catalog_enabled:
        return RemoteCatalogSyncResult(
            status="disabled",
            detail="Remote catalog is disabled.",
        )
    if not cfg.remote_catalog_repo_url:
        return RemoteCatalogSyncResult(
            status="skipped",
            detail="Remote catalog enabled but repo_url is not configured.",
        )

    repo_url = cfg.remote_catalog_repo_url
    branch = (cfg.remote_catalog_branch or "main").strip() or "main"
    target = Path(cfg.remote_catalog_local_path).expanduser()
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)

    git_dir = target / ".git"
    if git_dir.is_dir():
        _run_git(["fetch", "--prune", "origin"], cwd=target)
        _run_git(["checkout", branch], cwd=target)
        _run_git(["pull", "--ff-only", "origin", branch], cwd=target)
    else:
        if target.exists() and any(target.iterdir()):
            raise ValueError(
                f"Remote catalog path exists and is not an empty git repo: {target}"
            )
        _run_git(
            ["clone", "--branch", branch, "--single-branch", repo_url, str(target)]
        )

    commit = _run_git(["rev-parse", "HEAD"], cwd=target)
    return RemoteCatalogSyncResult(
        status="ok",
        detail=f"Remote catalog synced from {repo_url} ({branch}).",
        commit=commit,
        local_path=str(target),
    )

