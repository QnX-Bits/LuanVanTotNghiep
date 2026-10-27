from __future__ import annotations

import json
import os
import ssl
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import JSON, TypeDecorator


class Base(DeclarativeBase):
    pass


class DemoUser(Base):
    __tablename__ = "pvn_users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="vi")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ResultVersion(Base):
    __tablename__ = "pvn_result_versions"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    panel_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    result_files: Mapped[list["ResultFile"]] = relationship(back_populates="version", cascade="all, delete-orphan")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResultFile(Base):
    __tablename__ = "pvn_result_files"
    version_id: Mapped[str] = mapped_column(ForeignKey("pvn_result_versions.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), primary_key=True)
    compressed_content: Mapped[bytes] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped["ResultVersion"] = relationship(back_populates="result_files")


class ExecutionRules(Base):
    __tablename__ = "pvn_execution_rules"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Plan(Base):
    __tablename__ = "pvn_plans"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("pvn_result_versions.id"), nullable=False)
    execution_rules_id: Mapped[str] = mapped_column(ForeignKey("pvn_execution_rules.id"), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class ShareLink(Base):
    __tablename__ = "pvn_share_links"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("pvn_plans.code"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NewsArticle(Base):
    __tablename__ = "pvn_news_articles"
    slug: Mapped[str] = mapped_column(String(220), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    article: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    auto_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    panel_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PipelineRun(Base):
    __tablename__ = "pvn_pipeline_runs"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(24), nullable=False, default="backtest")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_by: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    log_tail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_version_id: Mapped[str | None] = mapped_column(String(48), nullable=True)


class AuditLog(Base):
    __tablename__ = "pvn_audit_logs"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PlanSequence(Base):
    __tablename__ = "pvn_plan_sequences"
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def _optional_ssl_string(options: dict[str, Any], key: str) -> str | None:
    value = options.pop(key, None)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"MySQL SSL option {key} must be a string")
    return value


def database_connection_settings(raw_url: str | None = None) -> tuple[URL, dict[str, Any]]:
    configured_url = raw_url if raw_url is not None else os.getenv("DATABASE_URL", "sqlite:///./portfolio_demo.db")
    url = make_url(configured_url)
    if url.drivername == "mysql":
        url = url.set(drivername="mysql+pymysql")
    elif url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")

    connect_args: dict[str, Any] = {}
    ssl_value = url.query.get("ssl") if url.get_backend_name() == "mysql" else None
    if isinstance(ssl_value, str):
        try:
            ssl_options = json.loads(ssl_value)
        except json.JSONDecodeError:
            ssl_options = None
        if isinstance(ssl_options, bool):
            ssl_options = {"rejectUnauthorized": ssl_options}
        if isinstance(ssl_options, dict):
            ssl_options = dict(ssl_options)
            if "rejectUnauthorized" in ssl_options:
                verify_certificate = ssl_options.pop("rejectUnauthorized")
                if not isinstance(verify_certificate, bool):
                    raise ValueError("MySQL ssl.rejectUnauthorized must be a boolean")
                context = ssl.create_default_context(
                    cafile=_optional_ssl_string(ssl_options, "ca"),
                    capath=_optional_ssl_string(ssl_options, "capath"),
                )
                cert = _optional_ssl_string(ssl_options, "cert")
                key = _optional_ssl_string(ssl_options, "key")
                password = _optional_ssl_string(ssl_options, "password")
                cipher = _optional_ssl_string(ssl_options, "cipher")
                if ssl_options:
                    unsupported = ", ".join(sorted(ssl_options))
                    raise ValueError(f"Unsupported MySQL SSL options: {unsupported}")
                if cert or key:
                    if not cert:
                        raise ValueError("MySQL SSL client key requires a client certificate")
                    context.load_cert_chain(certfile=cert, keyfile=key, password=password)
                if cipher:
                    context.set_ciphers(cipher)
                if verify_certificate:
                    context.verify_mode = ssl.CERT_REQUIRED
                    context.check_hostname = True
                else:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                connect_args["ssl"] = context
            else:
                connect_args["ssl"] = ssl_options
            url = url.difference_update_query(["ssl"])

    return url, connect_args


DB_URL, DB_CONNECT_ARGS = database_connection_settings()
engine = create_engine(DB_URL, connect_args=DB_CONNECT_ARGS, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
