"""SQLite persistence for web UI jobs.

Uses its own table inside the existing catalog database to avoid
coupling job state to catalog migrations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, String, Text, DateTime, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Session

from stackwarden.paths import get_catalog_path
from stackwarden.web.jobs.models import JobRecord, JobStatus

log = logging.getLogger(__name__)


class _Base(DeclarativeBase):
    pass


class JobRow(_Base):
    __tablename__ = "web_jobs"

    job_id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="queued")
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    selection_json = Column(Text, nullable=False, default="{}")
    result_artifact_id = Column(String, nullable=True)
    result_tag = Column(String, nullable=True)
    error_summary = Column(Text, nullable=True)
    log_path = Column(String, nullable=False, default="")


class JobStore:
    """Thin SQLite layer for persisting job records."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path) if db_path else get_catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{path}", echo=False)
        _Base.metadata.create_all(self._engine)

    def _session(self) -> Session:
        return Session(self._engine)

    def insert(self, record: JobRecord) -> None:
        selection = json.dumps({
            "profile_id": record.profile_id,
            "stack_id": record.stack_id,
            "variants": record.variants,
            "flags": record.flags,
            "build_optimization": record.build_optimization,
        })
        with self._session() as s:
            s.add(JobRow(
                job_id=record.job_id,
                status=record.status.value,
                created_at=record.created_at,
                started_at=record.started_at,
                ended_at=record.ended_at,
                selection_json=selection,
                result_artifact_id=record.result_artifact_id,
                result_tag=record.result_tag,
                error_summary=record.error_message,
                log_path=record.log_path,
            ))
            s.commit()

    def update(self, record: JobRecord) -> None:
        with self._session() as s:
            s.execute(
                update(JobRow)
                .where(JobRow.job_id == record.job_id)
                .values(
                    status=record.status.value,
                    started_at=record.started_at,
                    ended_at=record.ended_at,
                    result_artifact_id=record.result_artifact_id,
                    result_tag=record.result_tag,
                    error_summary=record.error_message,
                )
            )
            s.commit()

    def get(self, job_id: str) -> JobRecord | None:
        with self._session() as s:
            row = s.get(JobRow, job_id)
            return _row_to_record(row) if row else None

    def list_recent(self, limit: int | None = 50, offset: int | None = None) -> list[JobRecord]:
        with self._session() as s:
            stmt = select(JobRow).order_by(JobRow.created_at.desc())
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)
            rows = s.execute(stmt).scalars().all()
            return [_row_to_record(r) for r in rows]

    def cancel_if_active(self, job_id: str) -> bool:
        """Atomically set status to canceled only if still queued/running.

        Returns True if the cancel took effect.
        """
        now = datetime.now(timezone.utc)
        with self._session() as s:
            result = s.execute(
                update(JobRow)
                .where(
                    JobRow.job_id == job_id,
                    JobRow.status.in_([
                        JobStatus.QUEUED.value,
                        JobStatus.RUNNING.value,
                    ]),
                )
                .values(
                    status=JobStatus.CANCELED.value,
                    ended_at=now,
                    error_summary="Canceled by user",
                )
            )
            s.commit()
            return result.rowcount > 0  # type: ignore[return-value]

    def mark_orphaned_running_as_failed(self) -> int:
        """On startup, mark any 'running' jobs as failed (stale from previous process)."""
        now = datetime.now(timezone.utc)
        with self._session() as s:
            result = s.execute(
                update(JobRow)
                .where(JobRow.status == JobStatus.RUNNING.value)
                .values(
                    status=JobStatus.FAILED.value,
                    ended_at=now,
                    error_summary="Server restarted while job was running",
                )
            )
            s.commit()
            return result.rowcount  # type: ignore[return-value]


def _row_to_record(row: JobRow) -> JobRecord:
    selection = json.loads(row.selection_json) if row.selection_json else {}
    return JobRecord(
        job_id=row.job_id,
        status=JobStatus(row.status),
        created_at=row.created_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        profile_id=selection.get("profile_id", ""),
        stack_id=selection.get("stack_id", ""),
        variants=selection.get("variants"),
        flags=selection.get("flags", {}),
        build_optimization=selection.get("build_optimization", {}),
        result_artifact_id=row.result_artifact_id,
        result_tag=row.result_tag,
        error_message=row.error_summary,
        log_path=row.log_path or "",
    )
