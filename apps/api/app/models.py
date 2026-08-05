from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def default_compiler_profile() -> dict[str, str]:
    return {
        "name": "source-aware",
        "version": "1.0.0",
        "path": "compiler-profiles/source-aware-v1.json",
    }


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(40), default="demo")
    compiler_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=default_compiler_profile)
    compilation_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    guest_operation_count: Mapped[int] = mapped_column(Integer, default=0)
    guest_mutation_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"
    __table_args__ = (
        UniqueConstraint("email", name="uq_waitlist_signups_email"),
        UniqueConstraint("user_id", name="uq_waitlist_signups_user_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    source: Mapped[str] = mapped_column(String(40), default="landing")
    consent_version: Mapped[str] = mapped_column(String(30), default="2026-08-04")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspaces_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_identity"),
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version"),
        CheckConstraint(
            "authority_status IN ('current', 'superseded', 'draft', 'reference')",
            name="ck_documents_authority_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    original_sha256: Mapped[str] = mapped_column(String(64))
    normalized_sha256: Mapped[str] = mapped_column(String(64))
    normalized_text: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100))
    line_count: Mapped[int] = mapped_column(Integer)
    token_estimate: Mapped[int] = mapped_column(Integer)
    origin: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    authority_owner: Mapped[str] = mapped_column(String(200), default="unspecified")
    authority_status: Mapped[str] = mapped_column(String(20), default="reference")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    authority_scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    version_label: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint("project_id", "stable_key", "revision"),
        CheckConstraint(
            "provenance_kind IN ('source_anchored', 'reviewer_authored_guidance')",
            name="ck_rules_provenance_kind",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
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
    provenance_kind: Mapped[str] = mapped_column(String(40), default="source_anchored")
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
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
    __table_args__ = (
        UniqueConstraint("project_id", "content_hash", name="uq_builds_project_content_hash"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30))
    input_manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    compiler_version: Mapped[str] = mapped_column(String(30))
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_map: Mapped[dict[str, Any]] = mapped_column(JSON)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlacementDecision(Base):
    __tablename__ = "placement_decisions"
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uq_placement_decisions_rule_version"),
        CheckConstraint("version >= 1", name="ck_placement_decisions_version"),
        CheckConstraint(
            "transform_kind IN ('verbatim', 'reviewed_normalization', "
            "'reviewer_authored_guidance', 'compiler_scaffold')",
            name="ck_placement_decisions_transform_kind",
        ),
        CheckConstraint(
            "disposition IN ('routed', 'blocked', 'unsupported', 'retired')",
            name="ck_placement_decisions_disposition",
        ),
        CheckConstraint(
            "review_status IN ('approved', 'needs_review')",
            name="ck_placement_decisions_review_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    profile_name: Mapped[str] = mapped_column(String(120))
    profile_version: Mapped[str] = mapped_column(String(40))
    destinations: Mapped[list[str]] = mapped_column(JSON, default=list)
    scope_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rendering: Mapped[str | None] = mapped_column(Text, nullable=True)
    transform_kind: Mapped[str] = mapped_column(String(40))
    disposition: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(20), default="needs_review")
    reviewer: Mapped[str] = mapped_column(String(200), default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GeneratedSpan(Base):
    __tablename__ = "generated_spans"
    __table_args__ = (
        Index("ix_generated_spans_build_artifact", "build_id", "artifact_path"),
        CheckConstraint("line_start >= 1", name="ck_generated_spans_line_start"),
        CheckConstraint("line_end >= line_start", name="ck_generated_spans_line_order"),
        CheckConstraint("utf8_byte_start >= 0", name="ck_generated_spans_byte_start"),
        CheckConstraint(
            "utf8_byte_end >= utf8_byte_start",
            name="ck_generated_spans_byte_order",
        ),
        CheckConstraint(
            "transform_kind IN ('verbatim', 'reviewed_normalization', "
            "'reviewer_authored_guidance', 'compiler_scaffold')",
            name="ck_generated_spans_transform_kind",
        ),
        CheckConstraint(
            "length(artifact_sha256) = 64",
            name="ck_generated_spans_artifact_sha256_length",
        ),
        CheckConstraint(
            "length(text_sha256) = 64",
            name="ck_generated_spans_text_sha256_length",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    build_id: Mapped[str] = mapped_column(ForeignKey("builds.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("rules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    placement_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("placement_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_path: Mapped[str] = mapped_column(String(500))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    line_start: Mapped[int] = mapped_column(Integer)
    line_end: Mapped[int] = mapped_column(Integer)
    utf8_byte_start: Mapped[int] = mapped_column(Integer)
    utf8_byte_end: Mapped[int] = mapped_column(Integer)
    transform_kind: Mapped[str] = mapped_column(String(40))
    text_sha256: Mapped[str] = mapped_column(String(64))
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("project_id", "stable_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    stable_key: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(240))
    provenance: Mapped[str] = mapped_column(String(80))
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default="approved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
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
    test_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    final_state_hash: Mapped[str] = mapped_column(String(64))
    first_divergence: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)


class TraceEventModel(Base):
    __tablename__ = "trace_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    result_id: Mapped[str] = mapped_column(
        ForeignKey("scenario_results.id", ondelete="CASCADE"), index=True
    )
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("run_id", "content_hash", name="uq_reports_run_content_hash"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    verdict: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    rendered_markdown: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "kind",
            "idempotency_key",
            name="uq_jobs_workspace_project_kind_key",
        ),
        Index(
            "uq_jobs_one_running_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    cancellable: Mapped[bool] = mapped_column(Boolean, default=True)
