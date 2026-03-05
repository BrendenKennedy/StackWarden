"""Shared ensure pipeline — single execution path for both CLI and wizard.

``ensure_internal()`` encapsulates the full resolve-and-build pipeline:
profile/stack loading, variant validation, base digest resolution,
catalog upsert, and plan execution.  Both ``cli.py:ensure()`` and the
wizard's ``--run`` mode call this function.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pathlib import Path

    from stackwarden.domain.models import ArtifactRecord, Plan

from stackwarden.catalog.store import CatalogStore
from stackwarden.runtime.docker_client import DockerClient

log = logging.getLogger(__name__)


def ensure_internal(
    profile_id: str,
    stack_id: str,
    variants: dict[str, bool | str] | None = None,
    *,
    rebuild: bool = False,
    upgrade_base: bool = False,
    immutable: bool = False,
    run_hooks: bool = True,
    explain: bool = False,
    build_log_path: Path | None = None,
    cancel_check: Callable[[], bool] | None = None,
    catalog: CatalogStore | None = None,
    docker: DockerClient | None = None,
) -> tuple[ArtifactRecord, Plan]:
    """Run the full ensure pipeline and return ``(record, plan)``.

    This is the single execution path shared by the ``ensure`` CLI command
    and the wizard's ``--run`` mode.  It handles:

    * Profile / stack loading and validation
    * Variant validation
    * Docker client setup
    * Plan resolution (with optional base-digest pinning)
    * Catalog upsert
    * Plan execution (with locking, drift checks, hooks)

    If *build_log_path* is provided it is forwarded to ``execute_plan`` so
    that build output is captured to a file (used by the web UI for SSE
    log streaming).
    """
    from stackwarden.config import (
        AppConfig,
        compatibility_strict_default,
        load_block,
        load_profile,
        load_stack,
    )
    from stackwarden.domain.remote_catalog import sync_remote_catalog
    from stackwarden.domain.registry_policy import assert_registry_allowed
    from stackwarden.resolvers.resolver import resolve
    from stackwarden.builders.plan_executor import execute_plan
    from stackwarden.domain.errors import CancellationRequestedError
    from stackwarden.domain.variants import validate_variant_flags

    def _raise_if_canceled() -> None:
        if cancel_check and cancel_check():
            raise CancellationRequestedError("Build canceled by user request")

    _raise_if_canceled()
    cfg = AppConfig.load()
    if cfg.remote_catalog_enabled and cfg.remote_catalog_auto_pull:
        try:
            sync_remote_catalog(cfg)
        except Exception as exc:
            log.warning("Remote catalog sync failed; continuing with local data: %s", exc)
    _raise_if_canceled()

    p = load_profile(profile_id)
    s = load_stack(stack_id)
    blocks = [load_block(block_id) for block_id in (s.blocks or [])]
    _raise_if_canceled()

    if variants:
        validate_variant_flags(s, variants)

    if docker is None:
        docker = DockerClient()

    base_digest = None
    result = resolve(
        p,
        s,
        blocks=blocks,
        variants=variants,
        explain=explain,
        strict_mode=compatibility_strict_default(),
    )
    assert_registry_allowed(result.decision.base_image, cfg.registry)
    _raise_if_canceled()
    if not upgrade_base:
        try:
            base_digest = docker.get_image_digest(result.decision.base_image)
        except Exception as exc:
            log.debug("Could not resolve base digest (will proceed without): %s", exc)

    if base_digest:
        result = resolve(
            p,
            s,
            blocks=blocks,
            base_digest=base_digest,
            variants=variants,
            explain=explain,
            strict_mode=compatibility_strict_default(),
        )
    _raise_if_canceled()

    if catalog is None:
        catalog = CatalogStore(db_path=cfg.catalog_path)
    catalog.upsert_profile(p)
    catalog.upsert_stack(s)

    record = execute_plan(
        result, p, s, docker, catalog,
        rebuild=rebuild,
        immutable=immutable,
        run_hooks=run_hooks,
        build_log_path=build_log_path,
        should_cancel=cancel_check,
    )

    return record, result
