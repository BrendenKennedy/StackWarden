"""Configuration loading: profiles, stacks, and app-level settings."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from stackwarden.domain.composition import compose_stack
from stackwarden.domain.errors import (
    BlockNotFoundError,
    ProfileNotFoundError,
    StackNotFoundError,
    StackWardenError,
)
from stackwarden.domain.models import BlockSpec, Profile, StackRecipeSpec, StackSpec
from stackwarden.paths import get_config_path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DATA_DIR = _REPO_ROOT / "specs"


def _load_config_data() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _configured_remote_data_dir() -> Path | None:
    data = _load_config_data()
    remote = data.get("remote_catalog", {}) or {}
    enabled = bool(remote.get("enabled"))
    local_path = str(remote.get("local_path") or "").strip()
    if enabled and local_path:
        return Path(local_path).expanduser()
    return None


def _data_dir() -> Path:
    override = os.environ.get("STACKWARDEN_DATA_DIR")
    if override:
        return Path(override)
    configured_remote = _configured_remote_data_dir()
    if configured_remote:
        return configured_remote
    return _DEFAULT_DATA_DIR


def _configured_local_overrides_dir() -> Path | None:
    if os.environ.get("STACKWARDEN_DATA_DIR"):
        return None
    data = _load_config_data()
    remote = data.get("remote_catalog", {}) or {}
    enabled = bool(remote.get("enabled"))
    if not enabled:
        return None
    local_overrides = str(
        remote.get("local_overrides_path", "~/.local/share/stackwarden/local-catalog")
    ).strip()
    if not local_overrides:
        return None
    return Path(local_overrides).expanduser()


def _profiles_dir() -> Path:
    return _data_dir() / "profiles"


def _stacks_dir() -> Path:
    return _data_dir() / "stacks"


def _blocks_dir() -> Path:
    return _data_dir() / "blocks"


def _templates_dir() -> Path:
    return _data_dir() / "templates"


def _templates_roots() -> list[Path]:
    """Template roots in search order (local, remote, bundled) so remote complements bundled."""
    return _spec_roots("templates")


def _rules_dir() -> Path:
    return _data_dir() / "rules"


def _hardware_catalog_path() -> Path:
    return _rules_dir() / "hardware_catalog.yaml"


def _block_catalog_path() -> Path:
    return _rules_dir() / "block_catalog.yaml"


def _tuple_catalog_path() -> Path:
    return _rules_dir() / "tuple_catalog.yaml"


def _tuple_catalog_roots() -> list[Path]:
    """Rules roots for tuple_catalog.yaml in merge order (default-first so bundled is base).
    Remote and local overlay onto bundled, matching profiles/stacks/blocks complement behavior.
    """
    roots = _spec_roots("rules")
    return list(reversed(roots))


def _spec_roots(kind: str) -> list[Path]:
    roots: list[Path] = []
    local_overrides = _configured_local_overrides_dir()
    if local_overrides:
        roots.append(local_overrides / kind)
    roots.append(_data_dir() / kind)

    # When remote catalog is enabled, also include bundled/local project specs so
    # UI/API views can show a merged catalog (local + remote) without requiring
    # users to copy files into remote overlay directories.
    if not os.environ.get("STACKWARDEN_DATA_DIR"):
        roots.append(_DEFAULT_DATA_DIR / kind)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(root)
    return deduped


def _find_spec_path(kind: str, name: str, suffix: str) -> Path | None:
    for root in _spec_roots(kind):
        path = _safe_resolve(root, name, suffix)
        if path.exists():
            return path
    return None


def _spec_origin(kind: str, name: str) -> dict[str, str] | None:
    cfg = AppConfig.load()
    return _spec_origin_with_cfg(kind, name, cfg)


def _spec_origin_with_cfg(kind: str, name: str, cfg: "AppConfig") -> dict[str, str] | None:
    path = _find_spec_path(kind, name, ".yaml")
    if not path:
        return None
    local_overrides = _configured_local_overrides_dir()
    remote_data = _configured_remote_data_dir()
    source = "local"
    if local_overrides and path.is_relative_to(local_overrides.resolve()):
        source = "local"
    elif remote_data and path.is_relative_to(remote_data.resolve()):
        source = "remote"
    elif path.is_relative_to(_DEFAULT_DATA_DIR.resolve()):
        source = "bundled"

    repo_url = cfg.remote_catalog_repo_url if source == "remote" else None
    repo_owner = _repo_owner_from_url(repo_url) if repo_url else None
    return {
        "source": source,
        "source_path": str(path),
        "source_repo_url": repo_url or "",
        "source_repo_owner": repo_owner or "",
    }


def _repo_owner_from_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip()
    if cleaned.startswith("git@"):
        # e.g. git@github.com:owner/repo.git
        m = re.match(r"^git@[^:]+:([^/]+)/[^/]+(?:\.git)?$", cleaned)
        return m.group(1) if m else None
    m = re.match(r"^(?:https?://)?[^/]+/([^/]+)/[^/]+(?:\.git)?$", cleaned)
    return m.group(1) if m else None


def list_profile_ids() -> list[str]:
    ids: set[str] = set()
    for d in _spec_roots("profiles"):
        if d.is_dir():
            ids.update(p.stem for p in d.glob("*.yaml"))
    return sorted(ids)


def list_stack_ids() -> list[str]:
    ids: set[str] = set()
    for d in _spec_roots("stacks"):
        if d.is_dir():
            ids.update(p.stem for p in d.glob("*.yaml"))
    return sorted(ids)


def list_block_ids() -> list[str]:
    ids: set[str] = set()
    for d in _spec_roots("blocks"):
        if d.is_dir():
            ids.update(p.stem for p in d.glob("*.yaml"))
    return sorted(ids)


def _safe_resolve(base: Path, name: str, suffix: str) -> Path:
    """Resolve *name* within *base*, rejecting path traversal attempts."""
    path = (base / f"{name}{suffix}").resolve()
    if not path.is_relative_to(base.resolve()):
        raise StackWardenError(f"Invalid identifier (path traversal rejected): {name!r}")
    return path


def load_profile(profile_id: str) -> Profile:
    path = _find_spec_path("profiles", profile_id, ".yaml")
    if not path:
        raise ProfileNotFoundError(profile_id)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    try:
        return Profile.model_validate(data)
    except PydanticValidationError as exc:
        raise StackWardenError(f"Invalid profile '{profile_id}': {exc}") from exc


def load_stack(stack_id: str) -> StackSpec:
    path = _find_spec_path("stacks", stack_id, ".yaml")
    if not path:
        raise StackNotFoundError(stack_id)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    try:
        kind = data.get("kind", "stack")
        if kind == "stack":
            return StackSpec.model_validate(data)
        if kind == "stack_recipe":
            recipe = StackRecipeSpec.model_validate(data)
            blocks = [load_block(block_id) for block_id in recipe.blocks]
            return compose_stack(recipe, blocks)
        raise StackWardenError(
            f"Invalid stack '{stack_id}': unknown kind {kind!r}. "
            "Expected one of: stack, stack_recipe."
        )
    except PydanticValidationError as exc:
        raise StackWardenError(f"Invalid stack '{stack_id}': {exc}") from exc
    except ValueError as exc:
        raise StackWardenError(f"Invalid stack '{stack_id}': {exc}") from exc


def load_stack_spec_raw(stack_id: str) -> dict:
    """Load a stack YAML document exactly as-authored (without recipe composition)."""
    path = _find_spec_path("stacks", stack_id, ".yaml")
    if not path:
        raise StackNotFoundError(stack_id)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_block(block_id: str) -> BlockSpec:
    path = _find_spec_path("blocks", block_id, ".yaml")
    if not path:
        raise BlockNotFoundError(block_id)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    try:
        kind = data.get("kind")
        if kind is None:
            raise StackWardenError(
                f"Invalid block '{block_id}': missing kind. Expected 'kind: block'."
            )
        if kind != "block":
            raise StackWardenError(
                f"Invalid block '{block_id}': unknown kind {kind!r}. Expected 'block'."
            )
        return BlockSpec.model_validate(data)
    except PydanticValidationError as exc:
        raise StackWardenError(f"Invalid block '{block_id}': {exc}") from exc


def templates_dir() -> Path:
    return _templates_dir()


def templates_roots() -> list[Path]:
    """Template search roots (local, remote, bundled) for complement behavior."""
    return _templates_roots()


def rules_dir() -> Path:
    return _rules_dir()


def hardware_catalog_path() -> Path:
    return _hardware_catalog_path()


def block_catalog_path() -> Path:
    return _block_catalog_path()


def tuple_catalog_path() -> Path:
    return _tuple_catalog_path()


def tuple_catalog_roots() -> list[Path]:
    """Rules roots for tuple_catalog.yaml in merge order (bundled first, then remote, local)."""
    return _tuple_catalog_roots()


def compatibility_strict_default() -> bool:
    return os.environ.get("STACKWARDEN_COMPAT_STRICT", "").strip().lower() in {"1", "true", "yes", "on"}


def tuple_layer_mode() -> str:
    cfg = AppConfig.load()
    if cfg.tuple_layer_mode and cfg.tuple_layer_mode.strip():
        mode = cfg.tuple_layer_mode.strip().lower()
        if mode in {"off", "shadow", "warn", "enforce"}:
            return mode
    mode = os.environ.get("STACKWARDEN_TUPLE_LAYER_MODE", "enforce").strip().lower()
    if mode in {"off", "shadow", "warn", "enforce"}:
        return mode
    return "enforce"


def get_stacks_dir() -> Path:
    """Public accessor — same directory that :func:`load_stack` reads from."""
    local_overrides = _configured_local_overrides_dir()
    if local_overrides:
        return local_overrides / "stacks"
    return _stacks_dir()


def get_profiles_dir() -> Path:
    """Public accessor — same directory that :func:`load_profile` reads from."""
    local_overrides = _configured_local_overrides_dir()
    if local_overrides:
        return local_overrides / "profiles"
    return _profiles_dir()


def get_blocks_dir() -> Path:
    """Public accessor — same directory that :func:`load_block` reads from."""
    local_overrides = _configured_local_overrides_dir()
    if local_overrides:
        return local_overrides / "blocks"
    return _blocks_dir()


def get_profile_origin(profile_id: str) -> dict[str, str] | None:
    return _spec_origin("profiles", profile_id)


def get_stack_origin(stack_id: str) -> dict[str, str] | None:
    return _spec_origin("stacks", stack_id)


def get_block_origin(block_id: str) -> dict[str, str] | None:
    return _spec_origin("blocks", block_id)


def get_profile_origins(profile_ids: list[str]) -> dict[str, dict[str, str]]:
    cfg = AppConfig.load()
    return {pid: (_spec_origin_with_cfg("profiles", pid, cfg) or {}) for pid in profile_ids}


def get_stack_origins(stack_ids: list[str]) -> dict[str, dict[str, str]]:
    cfg = AppConfig.load()
    return {sid: (_spec_origin_with_cfg("stacks", sid, cfg) or {}) for sid in stack_ids}


def get_block_origins(block_ids: list[str]) -> dict[str, dict[str, str]]:
    cfg = AppConfig.load()
    return {bid: (_spec_origin_with_cfg("blocks", bid, cfg) or {}) for bid in block_ids}


# ---------------------------------------------------------------------------
# App-level config (~/.config/stackwarden/config.yaml)
# ---------------------------------------------------------------------------

class AppConfig:
    """Lightweight wrapper around user-level defaults."""

    def __init__(self, data: dict | None = None) -> None:
        data = data or {}
        self.default_profile: str | None = data.get("default_profile")
        self.catalog_path: str | None = data.get("catalog_path")
        self.tuple_layer_mode: str | None = data.get("tuple_layer_mode")
        self.log_dir: str | None = data.get("log_dir")

        from stackwarden.domain.registry_policy import RegistryPolicy
        reg = data.get("registry", {}) or {}
        self.registry: RegistryPolicy = RegistryPolicy(
            allow=reg.get("allow", []),
            deny=reg.get("deny", []),
        )
        remote = data.get("remote_catalog", {}) or {}
        self.remote_catalog_enabled: bool = bool(remote.get("enabled", False))
        self.remote_catalog_repo_url: str | None = (
            str(remote.get("repo_url", "")).strip() or None
        )
        self.remote_catalog_branch: str = (
            str(remote.get("branch", "main")).strip() or "main"
        )
        self.remote_catalog_local_path: str = (
            str(remote.get("local_path", "~/.local/share/stackwarden/remote-catalog")).strip()
            or "~/.local/share/stackwarden/remote-catalog"
        )
        self.remote_catalog_local_overrides_path: str = (
            str(
                remote.get(
                    "local_overrides_path",
                    "~/.local/share/stackwarden/local-catalog",
                )
            ).strip()
            or "~/.local/share/stackwarden/local-catalog"
        )
        self.remote_catalog_auto_pull: bool = bool(remote.get("auto_pull", True))

    @classmethod
    def load(cls) -> AppConfig:
        return cls(_load_config_data())

    def to_dict(self) -> dict:
        return {
            "default_profile": self.default_profile,
            "catalog_path": self.catalog_path,
            "tuple_layer_mode": self.tuple_layer_mode,
            "log_dir": self.log_dir,
            "registry": {
                "allow": list(self.registry.allow),
                "deny": list(self.registry.deny),
            },
            "remote_catalog": {
                "enabled": self.remote_catalog_enabled,
                "repo_url": self.remote_catalog_repo_url,
                "branch": self.remote_catalog_branch,
                "local_path": self.remote_catalog_local_path,
                "local_overrides_path": self.remote_catalog_local_overrides_path,
                "auto_pull": self.remote_catalog_auto_pull,
            },
        }

    def save(self) -> None:
        from stackwarden.web.util.write_yaml import atomic_write_yaml

        atomic_write_yaml(self.to_dict(), get_config_path())
