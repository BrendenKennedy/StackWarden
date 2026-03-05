"""SQLite persistence for single-admin auth credentials and sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Session, mapped_column

from stackwarden.paths import get_catalog_path


class _Base(DeclarativeBase):
    pass


class AdminCredentialRow(_Base):
    __tablename__ = "web_admin_credentials"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    username = mapped_column(String, nullable=False, unique=True)
    password_hash = mapped_column(String, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)


class SessionRow(_Base):
    __tablename__ = "web_auth_sessions"

    session_id = mapped_column(String, primary_key=True)
    admin_id = mapped_column(Integer, nullable=False, index=True)
    token_hash = mapped_column(String, nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    expires_at = mapped_column(DateTime, nullable=False)
    last_seen_at = mapped_column(DateTime, nullable=False)
    revoked = mapped_column(Boolean, nullable=False, default=False)


@dataclass
class AdminCredential:
    id: int
    username: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


class AuthStore:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path) if db_path else get_catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{path}", echo=False)
        _Base.metadata.create_all(self._engine)

    def _session(self) -> Session:
        return Session(self._engine)

    def has_admin(self) -> bool:
        with self._session() as s:
            return s.execute(select(AdminCredentialRow.id).limit(1)).first() is not None

    def get_admin_by_username(self, username: str) -> AdminCredential | None:
        with self._session() as s:
            row = s.execute(
                select(AdminCredentialRow).where(AdminCredentialRow.username == username)
            ).scalar_one_or_none()
            return _admin_from_row(row) if row else None

    def get_admin_by_id(self, admin_id: int) -> AdminCredential | None:
        with self._session() as s:
            row = s.get(AdminCredentialRow, admin_id)
            return _admin_from_row(row) if row else None

    def create_admin(self, username: str, password_hash: str) -> AdminCredential:
        now = self._now()
        with self._session() as s:
            row = AdminCredentialRow(
                username=username,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return _admin_from_row(row)

    def update_password(self, admin_id: int, password_hash: str) -> None:
        now = self._now()
        with self._session() as s:
            s.execute(
                update(AdminCredentialRow)
                .where(AdminCredentialRow.id == admin_id)
                .values(password_hash=password_hash, updated_at=now)
            )
            s.commit()

    def create_session(self, admin_id: int, session_id: str, token_hash: str, ttl_hours: int) -> datetime:
        now = self._now()
        expires_at = now + timedelta(hours=ttl_hours)
        with self._session() as s:
            s.add(
                SessionRow(
                    session_id=session_id,
                    admin_id=admin_id,
                    token_hash=token_hash,
                    created_at=now,
                    expires_at=expires_at,
                    last_seen_at=now,
                    revoked=False,
                )
            )
            s.commit()
        return expires_at

    def validate_session(self, session_id: str, token_hash: str) -> AdminCredential | None:
        now = self._now()
        with self._session() as s:
            row = s.get(SessionRow, session_id)
            if not row:
                return None
            if row.revoked or row.token_hash != token_hash or row.expires_at < now:
                return None
            row.last_seen_at = now
            s.commit()
            admin = s.get(AdminCredentialRow, row.admin_id)
            return _admin_from_row(admin) if admin else None

    def revoke_session(self, session_id: str) -> None:
        with self._session() as s:
            s.execute(
                update(SessionRow)
                .where(SessionRow.session_id == session_id)
                .values(revoked=True)
            )
            s.commit()

    def revoke_all_sessions(self, admin_id: int) -> None:
        with self._session() as s:
            s.execute(
                update(SessionRow)
                .where(SessionRow.admin_id == admin_id)
                .values(revoked=True)
            )
            s.commit()

def _admin_from_row(row: AdminCredentialRow) -> AdminCredential:
    return AdminCredential(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
