from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(40), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("project_id", "name", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    original_sha256: Mapped[str] = mapped_column(String(64))
    normalized_text: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100))
    line_count: Mapped[int] = mapped_column(Integer)
    token_estimate: Mapped[int] = mapped_column(Integer)
    origin: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (UniqueConstraint("project_id", "stable_key", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    stable_key: Mapped[str] = mapped_column(String(140), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240))
    normative_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    effect: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    condition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requires: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    enforcement: Mapped[str] = mapped_column(String(30))
    decidability: Mapped[str] = mapped_column(String(30))
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    target_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    exceptions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    related_rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    proof_status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    witness: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolution_state: Mapped[str] = mapped_column(String(30), default="open")
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Build(Base):
    __tablename__ = "builds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    input_manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    compiler_version: Mapped[str] = mapped_column(String(30))
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_map: Mapped[dict[str, Any]] = mapped_column(JSON)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("project_id", "stable_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    stable_key: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(240))
    provenance: Mapped[str] = mapped_column(String(80))
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default="approved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id"))
    requested_arms: Mapped[list[str]] = mapped_column(JSON)
    adapter: Mapped[str] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dataset_manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScenarioResult(Base):
    __tablename__ = "scenario_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id"), index=True)
    arm: Mapped[str] = mapped_column(String(40))
    verdict: Mapped[str] = mapped_column(String(20))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    final_state_hash: Mapped[str] = mapped_column(String(64))
    first_divergence: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)


class TraceEventModel(Base):
    __tablename__ = "trace_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    result_id: Mapped[str] = mapped_column(ForeignKey("scenario_results.id", ondelete="CASCADE"), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    rendered_markdown: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    cancellable: Mapped[bool] = mapped_column(Boolean, default=True)
