"""Create the original Aletheia modular-monolith schema.

Revision ID: 0001_initial
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("original_sha256", sa.String(64), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("origin", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "name", "version", name="uq_documents_version"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])

    op.create_table(
        "rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("stable_key", sa.String(140), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("normative_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("effect", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("requires", sa.JSON(), nullable=False),
        sa.Column("enforcement", sa.String(30), nullable=False),
        sa.Column("decidability", sa.String(30), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("target_tools", sa.JSON(), nullable=False),
        sa.Column("exceptions", sa.JSON(), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "stable_key", "revision", name="uq_rules_revision"),
    )
    op.create_index("ix_rules_project_id", "rules", ["project_id"])
    op.create_index("ix_rules_stable_key", "rules", ["stable_key"])

    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("related_rule_ids", sa.JSON(), nullable=False),
        sa.Column("proof_status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("witness", sa.JSON(), nullable=False),
        sa.Column("resolution_state", sa.String(30), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_findings_project_id", "findings", ["project_id"])

    op.create_table(
        "builds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("compiler_version", sa.String(30), nullable=False),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column("source_map", sa.JSON(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("content_hash", name="uq_builds_content_hash"),
    )
    op.create_index("ix_builds_project_id", "builds", ["project_id"])

    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("stable_key", sa.String(160), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("provenance", sa.String(80), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "stable_key", name="uq_test_cases_stable_key"),
    )
    op.create_index("ix_test_cases_project_id", "test_cases", ["project_id"])

    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("build_id", sa.String(36), nullable=False),
        sa.Column("requested_arms", sa.JSON(), nullable=False),
        sa.Column("adapter", sa.String(60), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("dataset_manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"]),
    )
    op.create_index("ix_runs_project_id", "runs", ["project_id"])

    op.create_table(
        "scenario_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("test_case_id", sa.String(36), nullable=False),
        sa.Column("arm", sa.String(40), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("final_state_hash", sa.String(64), nullable=False),
        sa.Column("first_divergence", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"]),
    )
    op.create_index("ix_scenario_results_run_id", "scenario_results", ["run_id"])
    op.create_index("ix_scenario_results_test_case_id", "scenario_results", ["test_case_id"])
    op.create_index("ix_scenario_results_trace_id", "scenario_results", ["trace_id"])

    op.create_table(
        "trace_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("result_id", sa.String(36), nullable=False),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["result_id"], ["scenario_results.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_trace_events_result_id", "trace_events", ["result_id"])
    op.create_index("ix_trace_events_trace_id", "trace_events", ["trace_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("verdict", sa.String(40), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("rendered_markdown", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.UniqueConstraint("content_hash", name="uq_reports_content_hash"),
    )
    op.create_index("ix_reports_run_id", "reports", ["run_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("lease_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancellable", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_index("ix_reports_run_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_trace_events_trace_id", table_name="trace_events")
    op.drop_index("ix_trace_events_result_id", table_name="trace_events")
    op.drop_table("trace_events")
    op.drop_index("ix_scenario_results_trace_id", table_name="scenario_results")
    op.drop_index("ix_scenario_results_test_case_id", table_name="scenario_results")
    op.drop_index("ix_scenario_results_run_id", table_name="scenario_results")
    op.drop_table("scenario_results")
    op.drop_index("ix_runs_project_id", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_test_cases_project_id", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_index("ix_builds_project_id", table_name="builds")
    op.drop_table("builds")
    op.drop_index("ix_findings_project_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_rules_stable_key", table_name="rules")
    op.drop_index("ix_rules_project_id", table_name="rules")
    op.drop_table("rules")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
