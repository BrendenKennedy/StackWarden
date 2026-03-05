"""Job data models for the web UI."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    profile_id: str
    stack_id: str
    variants: dict[str, Any] | None = None
    flags: dict[str, bool] = Field(default_factory=dict)
    build_optimization: dict[str, Any] = Field(default_factory=dict)
    result_artifact_id: str | None = None
    result_tag: str | None = None
    error_message: str | None = None
    log_path: str = ""


class JobEvent(BaseModel):
    type: Literal["status", "log", "progress", "result", "error"]
    ts: datetime
    payload: str
