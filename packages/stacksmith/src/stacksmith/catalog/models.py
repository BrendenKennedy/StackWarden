"""SQLAlchemy ORM models for the Stacksmith catalog."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    arch = Column(String, nullable=False)
    cuda_variant = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    artifacts = relationship("ArtifactRow", back_populates="profile")


class StackRow(Base):
    __tablename__ = "stacks"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    task = Column(String, nullable=False)
    serve = Column(String, nullable=False)
    api = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    artifacts = relationship("ArtifactRow", back_populates="stack")


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True)
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    stack_id = Column(String, ForeignKey("stacks.id"), nullable=False)
    tag = Column(String, unique=True, nullable=False)
    fingerprint = Column(String, nullable=False, unique=True, index=True)
    image_id = Column(String, nullable=True)
    digest = Column(String, nullable=True)
    base_image = Column(String, nullable=False)
    base_digest = Column(String, nullable=True)
    build_strategy = Column(String, nullable=False)
    template_hash = Column(String, nullable=True)
    stack_schema_version = Column(Integer, default=1)
    profile_schema_version = Column(Integer, default=1)
    block_schema_version = Column(Integer, default=1)
    status = Column(String, nullable=False, default="planned")
    manifest_path = Column(String, nullable=True)
    sbom_path = Column(String, nullable=True)
    profile_snapshot_path = Column(String, nullable=True)
    stack_snapshot_path = Column(String, nullable=True)
    plan_path = Column(String, nullable=True)
    variant_json = Column(Text, nullable=True)
    host_id = Column(String, nullable=True)
    docker_context = Column(String, nullable=True)
    daemon_arch = Column(String, nullable=True)
    stale_reason = Column(String, nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    profile = relationship("ProfileRow", back_populates="artifacts")
    stack = relationship("StackRow", back_populates="artifacts")
    components = relationship(
        "ArtifactComponentRow", back_populates="artifact", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_artifacts_profile_stack", "profile_id", "stack_id"),
    )


class ArtifactComponentRow(Base):
    __tablename__ = "artifact_components"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String, ForeignKey("artifacts.id"), nullable=False)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, default="")
    license_spdx = Column(String, nullable=True)
    license_severity = Column(String, nullable=True)

    artifact = relationship("ArtifactRow", back_populates="components")
