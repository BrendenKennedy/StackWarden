"""CatalogStore — SQLite persistence for profiles, stacks, and artifacts."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, delete, event, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from stackwarden.catalog.models import (
    ArtifactComponentRow,
    ArtifactRow,
    Base,
    ProfileRow,
    StackRow,
)
from stackwarden.catalog.migrations import run_migrations
from stackwarden.domain.enums import ArtifactStatus
from stackwarden.domain.errors import CatalogError
from stackwarden.paths import get_catalog_path

if TYPE_CHECKING:
    from stackwarden.domain.models import (
        ArtifactComponent,
        ArtifactRecord,
        Profile,
        StackSpec,
    )

log = logging.getLogger(__name__)


class CatalogStore:
    """SQLite-backed catalog for StackWarden artifacts."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path) if db_path else get_catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            f"sqlite:///{path}",
            echo=False,
            connect_args={"timeout": 30, "check_same_thread": False},
        )
        if self._engine.url.get_backend_name() == "sqlite":
            @event.listens_for(self._engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-redef]
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
        Base.metadata.create_all(self._engine)
        run_migrations(self._engine)

    def _session(self) -> Session:
        return Session(self._engine)

    def _commit_with_retry(self, s: Session, *, attempts: int = 3) -> None:
        for attempt in range(1, attempts + 1):
            try:
                s.commit()
                return
            except OperationalError as exc:
                msg = str(exc).lower()
                if "database is locked" not in msg and "database table is locked" not in msg:
                    raise
                s.rollback()
                if attempt >= attempts:
                    raise CatalogError("Catalog database is busy/locked; please retry") from exc
                time.sleep(0.05 * attempt)

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def upsert_profile(self, profile: Profile) -> None:
        with self._session() as s:
            existing = s.get(ProfileRow, profile.id)
            data = profile.model_dump_json()
            if existing:
                existing.display_name = profile.display_name
                existing.arch = profile.arch.value
                existing.cuda_variant = profile.cuda.variant if profile.cuda else "unknown"
                existing.data_json = data
            else:
                s.add(ProfileRow(
                    id=profile.id,
                    display_name=profile.display_name,
                    arch=profile.arch.value,
                    cuda_variant=profile.cuda.variant if profile.cuda else "unknown",
                    data_json=data,
                ))
            self._commit_with_retry(s)

    def list_profiles(self) -> list[dict]:
        with self._session() as s:
            rows = s.execute(select(ProfileRow)).scalars().all()
            return [
                {"id": r.id, "display_name": r.display_name, "arch": r.arch}
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Stacks
    # ------------------------------------------------------------------

    def upsert_stack(self, stack: StackSpec) -> None:
        with self._session() as s:
            existing = s.get(StackRow, stack.id)
            data = stack.model_dump_json()
            if existing:
                existing.display_name = stack.display_name
                existing.task = stack.task.value
                existing.serve = stack.serve.value
                existing.api = stack.api.value
                existing.data_json = data
            else:
                s.add(StackRow(
                    id=stack.id,
                    display_name=stack.display_name,
                    task=stack.task.value,
                    serve=stack.serve.value,
                    api=stack.api.value,
                    data_json=data,
                ))
            self._commit_with_retry(s)

    def list_stacks(self) -> list[dict]:
        with self._session() as s:
            rows = s.execute(select(StackRow)).scalars().all()
            return [
                {"id": r.id, "display_name": r.display_name, "task": r.task, "serve": r.serve}
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def insert_artifact(self, record: ArtifactRecord) -> None:
        try:
            with self._session() as s:
                s.add(ArtifactRow(
                    id=record.id,
                    profile_id=record.profile_id,
                    stack_id=record.stack_id,
                    tag=record.tag,
                    fingerprint=record.fingerprint,
                    image_id=record.image_id,
                    digest=record.digest,
                    base_image=record.base_image,
                    base_digest=record.base_digest,
                    build_strategy=record.build_strategy,
                    template_hash=record.template_hash,
                    stack_schema_version=record.stack_schema_version,
                    profile_schema_version=record.profile_schema_version,
                    block_schema_version=record.block_schema_version,
                    manifest_path=record.manifest_path,
                    sbom_path=record.sbom_path,
                    profile_snapshot_path=record.profile_snapshot_path,
                    stack_snapshot_path=record.stack_snapshot_path,
                    plan_path=record.plan_path,
                    variant_json=record.variant_json,
                    host_id=record.host_id,
                    docker_context=record.docker_context,
                    daemon_arch=record.daemon_arch,
                    status=record.status.value,
                    stale_reason=record.stale_reason,
                    error_detail=record.error_detail,
                    created_at=record.created_at,
                ))
                self._commit_with_retry(s)
        except IntegrityError as exc:
            raise CatalogError(
                f"Artifact with this fingerprint or tag already exists: "
                f"{record.fingerprint[:16]}"
            ) from exc

    def update_artifact(self, record: ArtifactRecord) -> None:
        with self._session() as s:
            row = s.get(ArtifactRow, record.id)
            if row:
                row.status = record.status.value
                row.image_id = record.image_id
                row.digest = record.digest
                row.manifest_path = record.manifest_path
                row.sbom_path = record.sbom_path
                row.profile_snapshot_path = record.profile_snapshot_path
                row.stack_snapshot_path = record.stack_snapshot_path
                row.plan_path = record.plan_path
                row.variant_json = record.variant_json
                row.stale_reason = record.stale_reason
                row.error_detail = record.error_detail
                self._commit_with_retry(s)

    def update_artifact_status(self, artifact_id: str, status: ArtifactStatus) -> None:
        with self._session() as s:
            s.execute(
                update(ArtifactRow)
                .where(ArtifactRow.id == artifact_id)
                .values(status=status.value)
            )
            self._commit_with_retry(s)

    def mark_stale(
        self, profile_id: str, stack_id: str, *, reason: str | None = None
    ) -> int:
        """Mark all non-stale/failed artifacts for this combo as stale.  Returns count."""
        with self._session() as s:
            values: dict = {"status": ArtifactStatus.STALE.value}
            if reason:
                values["stale_reason"] = reason
            result = s.execute(
                update(ArtifactRow)
                .where(
                    ArtifactRow.profile_id == profile_id,
                    ArtifactRow.stack_id == stack_id,
                    ArtifactRow.status.in_([
                        ArtifactStatus.BUILT.value,
                        ArtifactStatus.BUILDING.value,
                        ArtifactStatus.PLANNED.value,
                    ]),
                )
                .values(**values)
            )
            self._commit_with_retry(s)
            return result.rowcount  # type: ignore[return-value]

    def get_artifact_by_tag(self, tag: str) -> ArtifactRecord | None:
        with self._session() as s:
            row = s.execute(
                select(ArtifactRow).where(ArtifactRow.tag == tag)
            ).scalar_one_or_none()
            return _row_to_record(row) if row else None

    def get_artifact_by_fingerprint(self, fp: str) -> ArtifactRecord | None:
        with self._session() as s:
            row = s.execute(
                select(ArtifactRow).where(ArtifactRow.fingerprint == fp)
            ).scalar_one_or_none()
            return _row_to_record(row) if row else None

    def get_artifact_by_id(self, artifact_id: str) -> ArtifactRecord | None:
        with self._session() as s:
            row = s.get(ArtifactRow, artifact_id)
            return _row_to_record(row) if row else None

    def search_artifacts(
        self,
        profile_id: str | None = None,
        stack_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ArtifactRecord]:
        with self._session() as s:
            stmt = select(ArtifactRow)
            if profile_id:
                stmt = stmt.where(ArtifactRow.profile_id == profile_id)
            if stack_id:
                stmt = stmt.where(ArtifactRow.stack_id == stack_id)
            if status:
                stmt = stmt.where(ArtifactRow.status == status)
            if q:
                pattern = f"%{q}%"
                stmt = stmt.where(
                    ArtifactRow.tag.ilike(pattern)
                    | ArtifactRow.fingerprint.ilike(pattern)
                    | ArtifactRow.base_image.ilike(pattern)
                )
            stmt = stmt.order_by(ArtifactRow.created_at.desc())
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)
            rows = s.execute(stmt).scalars().all()
            return [_row_to_record(r) for r in rows]

    def get_newest_build(self, stack_id: str, profile_id: str) -> ArtifactRecord | None:
        with self._session() as s:
            row = s.execute(
                select(ArtifactRow)
                .where(
                    ArtifactRow.stack_id == stack_id,
                    ArtifactRow.profile_id == profile_id,
                    ArtifactRow.status == ArtifactStatus.BUILT.value,
                )
                .order_by(ArtifactRow.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            return _row_to_record(row) if row else None

    def prune_by_status(self, status: ArtifactStatus) -> int:
        with self._session() as s:
            result = s.execute(
                delete(ArtifactRow).where(ArtifactRow.status == status.value)
            )
            self._commit_with_retry(s)
            return result.rowcount  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Lifecycle / prune
    # ------------------------------------------------------------------

    def find_unused(self, *, force: bool = False) -> list["ArtifactRecord"]:
        """Find artifacts that are not the newest built per (profile, stack, variant).

        Unless *force* is True, the newest built artifact for each group is
        protected from pruning.
        """
        with self._session() as s:
            built = s.execute(
                select(ArtifactRow)
                .where(ArtifactRow.status == ArtifactStatus.BUILT.value)
                .order_by(ArtifactRow.created_at.desc())
            ).scalars().all()

        protected: set[str] = set()
        if not force:
            seen: set[tuple[str, str, str | None]] = set()
            for row in built:
                key = (row.profile_id, row.stack_id, getattr(row, "variant_json", None))
                if key not in seen:
                    seen.add(key)
                    protected.add(row.id)

        return [_row_to_record(r) for r in built if r.id not in protected]

    def prune_artifact(self, artifact_id: str | None) -> None:
        if not artifact_id:
            return
        with self._session() as s:
            row = s.get(ArtifactRow, artifact_id)
            if row:
                s.delete(row)
                self._commit_with_retry(s)

    def count_protected(self) -> int:
        """Count the number of newest-stable artifacts that would be protected."""
        with self._session() as s:
            built = s.execute(
                select(ArtifactRow)
                .where(ArtifactRow.status == ArtifactStatus.BUILT.value)
                .order_by(ArtifactRow.created_at.desc())
            ).scalars().all()
        seen: set[tuple[str, str, str | None]] = set()
        count = 0
        for row in built:
            key = (row.profile_id, row.stack_id, getattr(row, "variant_json", None))
            if key not in seen:
                seen.add(key)
                count += 1
        return count

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------

    def insert_components(self, components: list[ArtifactComponent]) -> None:
        with self._session() as s:
            for c in components:
                s.add(ArtifactComponentRow(
                    artifact_id=c.artifact_id,
                    type=c.type,
                    name=c.name,
                    version=c.version,
                    license_spdx=c.license_spdx,
                    license_severity=c.license_severity.value if c.license_severity else None,
                ))
            self._commit_with_retry(s)

    def get_components(self, artifact_id: str) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(ArtifactComponentRow)
                .where(ArtifactComponentRow.artifact_id == artifact_id)
            ).scalars().all()
            return [
                {
                    "type": r.type,
                    "name": r.name,
                    "version": r.version,
                    "license_spdx": r.license_spdx,
                    "license_severity": r.license_severity,
                }
                for r in rows
            ]


def _row_to_record(row: ArtifactRow) -> "ArtifactRecord":
    from stackwarden.domain.models import ArtifactRecord

    return ArtifactRecord(
        id=row.id,
        profile_id=row.profile_id,
        stack_id=row.stack_id,
        tag=row.tag,
        fingerprint=row.fingerprint,
        image_id=row.image_id,
        digest=row.digest,
        base_image=row.base_image,
        base_digest=row.base_digest,
        build_strategy=row.build_strategy,
        template_hash=row.template_hash,
        stack_schema_version=row.stack_schema_version or 1,
        profile_schema_version=getattr(row, "profile_schema_version", 1) or 1,
        block_schema_version=getattr(row, "block_schema_version", 1) or 1,
        manifest_path=row.manifest_path,
        sbom_path=row.sbom_path,
        profile_snapshot_path=row.profile_snapshot_path,
        stack_snapshot_path=row.stack_snapshot_path,
        plan_path=row.plan_path,
        variant_json=row.variant_json,
        host_id=row.host_id,
        docker_context=row.docker_context,
        daemon_arch=row.daemon_arch,
        status=ArtifactStatus(row.status),
        stale_reason=getattr(row, "stale_reason", None),
        error_detail=row.error_detail,
        created_at=row.created_at,
    )
