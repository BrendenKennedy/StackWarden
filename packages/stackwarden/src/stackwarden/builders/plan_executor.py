"""Plan executor — runs plan steps and manages artifact lifecycle.

Status lifecycle:
  1. Insert artifact with status=building BEFORE build starts
  2. On success: update to built, record image_id + digest
  3. On failure: update to failed, record error
  4. On rebuild: mark previous artifacts as stale first
"""

from __future__ import annotations

import json as _json
import logging
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Protocol

from stackwarden.domain.drift import detect_drift, drift_summary, is_stale
from stackwarden.domain.enums import ArtifactStatus, BuildStrategy
from stackwarden.domain.errors import BuildError, CancellationRequestedError, DriftError
from stackwarden.domain.locking import acquire_lock, compute_variant_hash
from stackwarden.domain.models import ArtifactRecord

if TYPE_CHECKING:
    from stackwarden.domain.models import Plan, Profile, StackSpec
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.runtime.docker_client import DockerClient

log = logging.getLogger(__name__)


@dataclass
class BuildResult:
    tag: str
    image_id: str | None = None
    digest: str | None = None


class Builder(Protocol):
    def can_build(self, plan: Plan) -> bool: ...
    def execute(self, plan: Plan, profile: Profile, stack: StackSpec,
                docker_client: DockerClient, service_root: Path | None = None) -> BuildResult: ...


class OverlayBuilder:
    def can_build(self, plan: Plan) -> bool:
        return plan.decision.builder == BuildStrategy.OVERLAY.value

    def execute(
        self,
        plan: Plan,
        profile: Profile,
        stack: StackSpec,
        docker_client: DockerClient,
        service_root: Path | None = None,
    ) -> BuildResult:
        from stackwarden.builders.overlay import build_overlay

        tag = build_overlay(plan, stack, profile, docker_client, service_root)
        image_id = docker_client.get_image_id(tag)
        digest = docker_client.get_image_digest(tag)
        return BuildResult(tag=tag, image_id=image_id, digest=digest)


class PullBuilder:
    def can_build(self, plan: Plan) -> bool:
        return plan.decision.builder == BuildStrategy.PULL.value

    def execute(
        self,
        plan: Plan,
        profile: Profile,
        stack: StackSpec,
        docker_client: DockerClient,
        service_root: Path | None = None,
    ) -> BuildResult:
        from stackwarden.builders.pull import build_pull

        tag = build_pull(plan, profile, docker_client)
        image_id = docker_client.get_image_id(tag)
        digest = docker_client.get_image_digest(tag)
        return BuildResult(tag=tag, image_id=image_id, digest=digest)


BUILDER_REGISTRY: dict[str, Builder] = {
    "overlay": OverlayBuilder(),
    "pull": PullBuilder(),
}


def check_existing(
    plan: Plan,
    docker_client: DockerClient,
    catalog: CatalogStore,
    *,
    immutable: bool = False,
) -> ArtifactRecord | None:
    """Check whether a usable image already exists.

    Returns the catalog record if the image is fresh, or ``None`` if a
    (re)build is required.  When *immutable* is ``True`` and drift is
    detected, a ``DriftError`` is raised instead of allowing a rebuild.
    """
    tag = plan.artifact.tag
    if not docker_client.image_exists(tag):
        if immutable:
            existing = catalog.get_artifact_by_tag(tag)
            if existing and existing.status == ArtifactStatus.BUILT:
                raise DriftError(
                    tag, "Image no longer present locally but catalog entry exists"
                )
        return None

    labels = docker_client.get_image_labels(tag)
    catalog_record = catalog.get_artifact_by_tag(tag)
    reasons = detect_drift(labels, catalog_record, plan)

    if not is_stale(reasons):
        log.info("Image %s exists with no drift — skipping build", tag)
        return catalog_record

    summary = drift_summary(reasons)
    if immutable:
        raise DriftError(tag, summary)

    log.warning("Image %s has drift (%s) — will rebuild", tag, summary)

    if catalog_record and catalog_record.status == ArtifactStatus.BUILT:
        catalog_record.status = ArtifactStatus.STALE
        catalog_record.stale_reason = summary
        catalog.update_artifact(catalog_record)

    return None


def execute_plan(
    plan: Plan,
    profile: Profile,
    stack: StackSpec,
    docker_client: DockerClient,
    catalog: CatalogStore,
    *,
    rebuild: bool = False,
    immutable: bool = False,
    run_hooks: bool = True,
    service_root: Path | None = None,
    build_log_path: Path | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ArtifactRecord:
    """Execute a resolved plan and persist the result in the catalog.

    If *build_log_path* is provided, a file handler is attached to the module
    logger for the duration of the build so that all log output is also
    written to that file (useful for the web UI SSE log streaming).
    """
    try:
        variant_data = _json.loads(plan.artifact.labels.get("stackwarden.variants", "{}"))
    except _json.JSONDecodeError:
        log.warning("Malformed stackwarden.variants label, treating as empty")
        variant_data = {}
    vh = compute_variant_hash(variant_data) if variant_data else ""

    with acquire_lock(plan.profile_id, plan.stack_id, vh):
        return _execute_plan_locked(
            plan, profile, stack, docker_client, catalog,
            rebuild=rebuild, immutable=immutable,
            run_hooks=run_hooks, service_root=service_root,
            build_log_path=build_log_path,
            should_cancel=should_cancel,
        )


def _execute_plan_locked(
    plan: Plan,
    profile: Profile,
    stack: StackSpec,
    docker_client: DockerClient,
    catalog: CatalogStore,
    *,
    rebuild: bool = False,
    immutable: bool = False,
    run_hooks: bool = True,
    service_root: Path | None = None,
    build_log_path: Path | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ArtifactRecord:
    """Inner execution path, called while holding the build lock."""
    fh = None
    if build_log_path:
        from stackwarden.logging import add_file_handler
        fh = add_file_handler(log, build_log_path)

    try:
        return _do_execute(
            plan, profile, stack, docker_client, catalog,
            rebuild=rebuild, immutable=immutable,
            run_hooks=run_hooks, service_root=service_root,
            should_cancel=should_cancel,
        )
    finally:
        if fh:
            log.removeHandler(fh)
            fh.close()


def _do_execute(
    plan: Plan,
    profile: Profile,
    stack: StackSpec,
    docker_client: DockerClient,
    catalog: CatalogStore,
    *,
    rebuild: bool = False,
    immutable: bool = False,
    run_hooks: bool = True,
    service_root: Path | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ArtifactRecord:
    """Core build logic, separated so _execute_plan_locked can manage log handler lifecycle."""
    if should_cancel and should_cancel():
        raise CancellationRequestedError("Build canceled before execution started")

    if not rebuild:
        existing = check_existing(
            plan, docker_client, catalog, immutable=immutable
        )
        if existing:
            return existing

    if should_cancel and should_cancel():
        raise CancellationRequestedError("Build canceled before lifecycle updates")

    catalog.mark_stale(plan.profile_id, plan.stack_id)

    # When rebuilding, remove existing artifact so insert can succeed (fingerprint is unique)
    existing = catalog.get_artifact_by_fingerprint(plan.artifact.fingerprint)
    if existing:
        catalog.prune_artifact(existing.id)

    record = _make_record(plan, status=ArtifactStatus.BUILDING)
    catalog.insert_artifact(record)

    builder_name = plan.decision.builder
    builder = BUILDER_REGISTRY.get(builder_name)
    if not builder:
        record.status = ArtifactStatus.FAILED
        record.error_detail = f"Unknown builder: {builder_name!r}"
        catalog.update_artifact(record)
        raise BuildError(builder_name, f"Unknown builder: {builder_name!r}")

    try:
        if should_cancel and should_cancel():
            record.status = ArtifactStatus.FAILED
            record.error_detail = "Build canceled before builder execution"
            catalog.update_artifact(record)
            raise CancellationRequestedError("Build canceled before builder execution")
        result = builder.execute(plan, profile, stack, docker_client, service_root)
        record.status = ArtifactStatus.BUILT
        record.image_id = result.image_id
        record.digest = result.digest
        catalog.update_artifact(record)
        log.info("Build succeeded: %s", result.tag)
    except BuildError:
        raise
    except CancellationRequestedError:
        raise
    except Exception as exc:
        record.status = ArtifactStatus.FAILED
        record.error_detail = str(exc)
        try:
            catalog.update_artifact(record)
        except Exception as update_exc:
            log.error("Failed to update artifact status to FAILED: %s", update_exc)
        raise BuildError(builder_name, str(exc)) from exc

    if should_cancel and should_cancel():
        record.status = ArtifactStatus.FAILED
        record.error_detail = "Build canceled after builder execution"
        catalog.update_artifact(record)
        raise CancellationRequestedError("Build canceled after builder execution")

    _capture_manifest(record, profile, stack, plan, catalog)
    _capture_snapshots(record, profile, stack, plan, catalog)

    if run_hooks:
        _run_hooks(record, profile, stack, catalog)

    return record


def _capture_manifest(
    record: ArtifactRecord,
    profile: Profile,
    stack: StackSpec,
    plan: Plan,
    catalog: CatalogStore,
) -> None:
    """Best-effort manifest capture after a successful build."""
    try:
        from stackwarden.runtime.manifest_capture import capture_manifest
        from stackwarden.domain.manifest import save_manifest

        manifest = capture_manifest(record.tag, profile, stack, plan)
        path = save_manifest(manifest)
        record.manifest_path = str(path)
        catalog.update_artifact(record)
        log.info("Manifest saved: %s", path)
    except Exception as exc:
        log.warning("Manifest capture failed (non-fatal): %s", exc)


def _capture_snapshots(
    record: ArtifactRecord,
    profile: Profile,
    stack: StackSpec,
    plan: Plan,
    catalog: CatalogStore,
) -> None:
    """Best-effort spec snapshot capture after a successful build."""
    try:
        from stackwarden.domain.snapshots import artifact_dir, write_snapshot_files

        art_dir = artifact_dir(record.fingerprint)
        snapshot_paths = write_snapshot_files(art_dir, profile, stack, plan)
        record.profile_snapshot_path = str(snapshot_paths.get("profile_snapshot_path", ""))
        record.stack_snapshot_path = str(snapshot_paths.get("stack_snapshot_path", ""))
        record.plan_path = str(snapshot_paths.get("plan_path", ""))
        catalog.update_artifact(record)
        log.info("Spec snapshots saved: %s", art_dir)
    except Exception as exc:
        log.warning("Snapshot capture failed (non-fatal): %s", exc)


def _run_hooks(
    record: ArtifactRecord,
    profile: Profile,
    stack: StackSpec,
    catalog: CatalogStore,
) -> None:
    """Run post-build validation hooks. Failures mark the artifact as failed
    but never delete the image."""
    import importlib.util
    if importlib.util.find_spec("stackwarden.hooks") is None:
        return
    from stackwarden.hooks import get_hooks

    failures: list[str] = []
    for hook in get_hooks():
        try:
            result = hook.run(record.tag, profile, stack)
            if not result.success:
                failures.append(f"[{hook.name}] {result.logs}")
            if result.warnings:
                for w in result.warnings:
                    log.warning("Hook %s: %s", hook.name, w)
        except Exception as exc:
            failures.append(f"[{hook.name}] {exc}")

    if failures:
        record.status = ArtifactStatus.FAILED
        record.error_detail = "Hook failures:\n" + "\n".join(failures)
        catalog.update_artifact(record)
        log.error("Post-build hooks failed for %s", record.tag)


def _make_record(plan: Plan, status: ArtifactStatus) -> ArtifactRecord:
    host_id = socket.gethostname()
    stack_schema_version = int(plan.artifact.labels.get("stackwarden.schema_version", "1") or "1")
    profile_schema_version = int(plan.artifact.labels.get("stackwarden.profile_schema_version", "1") or "1")
    block_schema_version = int(plan.artifact.labels.get("stackwarden.block_schema_version", "1") or "1")

    return ArtifactRecord(
        id=uuid.uuid4().hex[:16],
        profile_id=plan.profile_id,
        stack_id=plan.stack_id,
        tag=plan.artifact.tag,
        fingerprint=plan.artifact.fingerprint,
        base_image=plan.decision.base_image,
        base_digest=plan.decision.base_digest,
        build_strategy=plan.decision.builder,
        stack_schema_version=stack_schema_version,
        profile_schema_version=profile_schema_version,
        block_schema_version=block_schema_version,
        host_id=host_id,
        status=status,
    )
