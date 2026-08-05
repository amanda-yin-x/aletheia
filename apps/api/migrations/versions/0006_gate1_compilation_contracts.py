"""Add Gate 1 source-aware compilation persistence contracts.

Revision ID: 0006_gate1_compilation_contracts
Revises: 0005_guest_access_waitlist
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_gate1_compilation_contracts"
down_revision: str | None = "0005_guest_access_waitlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_COMPILER_PROFILE = {
    "name": "source-aware",
    "version": "1.0.0",
    "path": "compiler-profiles/source-aware-v1.json",
}
NORTHSTAR_COMPILATION_CONFIG = {
    "schema_version": "1.0",
    "bundle_slug": "refund-operations",
    "agent_label": "Northstar Retail support agent",
    "skill_title": "Refund operations",
    "knowledge_title": "Retail policy reference",
    "suite_name": "Aletheia-authored refund boundary suite",
    "suite_version": 3,
    "inputs": {
        "baseline_prompt": {"name": "baseline-system-prompt.md", "version": 1},
        "tool_schema": {"name": "tools.json", "version": 1},
        "evaluation_data": {"name": "orders.json", "version": 1},
    },
    "expected_context": [
        "prompt-kernel.md",
        "skills/refund-operations/SKILL.md",
        "knowledge/refund-operations.md",
    ],
}


def _json_default(value: object) -> sa.TextClause:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return sa.text(f"'{encoded}'")


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column(
                "compiler_profile",
                sa.JSON(),
                nullable=False,
                server_default=_json_default(DEFAULT_COMPILER_PROFILE),
            )
        )
        batch.add_column(
            sa.Column(
                "compilation_config",
                sa.JSON(),
                nullable=False,
                server_default=_json_default({}),
            )
        )

    projects = sa.table(
        "projects",
        sa.column("slug", sa.String(length=100)),
        sa.column("compilation_config", sa.JSON()),
    )
    bind.execute(
        projects.update()
        .where(projects.c.slug == "northstar-retail")
        .values(compilation_config=NORTHSTAR_COMPILATION_CONFIG)
    )

    if "documents" in existing_tables:
        with op.batch_alter_table("documents") as batch:
            batch.add_column(
                sa.Column(
                    "authority_owner",
                    sa.String(length=200),
                    nullable=False,
                    server_default="unspecified",
                )
            )
            batch.add_column(
                sa.Column(
                    "authority_status",
                    sa.String(length=20),
                    nullable=False,
                    server_default="reference",
                )
            )
            batch.add_column(
                sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch.add_column(
                sa.Column("supersedes_document_id", sa.String(length=36), nullable=True)
            )
            batch.add_column(
                sa.Column(
                    "jurisdictions",
                    sa.JSON(),
                    nullable=False,
                    server_default=_json_default([]),
                )
            )
            batch.add_column(
                sa.Column(
                    "authority_scopes",
                    sa.JSON(),
                    nullable=False,
                    server_default=_json_default([]),
                )
            )
            batch.add_column(
                sa.Column(
                    "version_label",
                    sa.String(length=80),
                    nullable=False,
                    server_default="",
                )
            )
            batch.create_foreign_key(
                "fk_documents_supersedes_document_id",
                "documents",
                ["supersedes_document_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_index(
                "ix_documents_supersedes_document_id", ["supersedes_document_id"]
            )
            batch.create_check_constraint(
                "ck_documents_authority_status",
                "authority_status IN ('current', 'superseded', 'draft', 'reference')",
            )

        rows = bind.execute(
            sa.text("SELECT id, kind, version, origin FROM documents")
        ).mappings()
        for row in rows:
            origin = row["origin"]
            if isinstance(origin, str):
                try:
                    origin = json.loads(origin)
                except json.JSONDecodeError:
                    origin = {}
            authored = (
                isinstance(origin, dict) and origin.get("type") == "aletheia_authored"
            )
            status = {
                "baseline_prompt": "current",
                "current_policy": "current",
                "stale_sop": "superseded",
                "tool_schema": "current",
                "evaluation_data": "reference",
                "style_guide": "reference",
            }.get(str(row["kind"]), "reference")
            bind.execute(
                sa.text(
                    "UPDATE documents SET authority_owner = :owner, "
                    "authority_status = :status, version_label = :version_label "
                    "WHERE id = :document_id"
                ),
                {
                    "document_id": row["id"],
                    "owner": "Aletheia fixture" if authored else "unspecified",
                    "status": status,
                    "version_label": f"v{row['version']}",
                },
            )

    if "rules" in existing_tables:
        with op.batch_alter_table("rules") as batch:
            batch.add_column(
                sa.Column(
                    "provenance_kind",
                    sa.String(length=40),
                    nullable=False,
                    server_default="source_anchored",
                )
            )
            batch.create_check_constraint(
                "ck_rules_provenance_kind",
                "provenance_kind IN ('source_anchored', 'reviewer_authored_guidance')",
            )
            batch.add_column(
                sa.Column(
                    "provenance_metadata",
                    sa.JSON(),
                    nullable=False,
                    server_default=_json_default({}),
                )
            )

    op.create_table(
        "placement_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("profile_name", sa.String(length=120), nullable=False),
        sa.Column("profile_version", sa.String(length=40), nullable=False),
        sa.Column("destinations", sa.JSON(), nullable=False),
        sa.Column("scope_slug", sa.String(length=120), nullable=True),
        sa.Column("rendering", sa.Text(), nullable=True),
        sa.Column("transform_kind", sa.String(length=40), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("reviewer", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("version >= 1", name="ck_placement_decisions_version"),
        sa.CheckConstraint(
            "transform_kind IN ('verbatim', 'reviewed_normalization', "
            "'reviewer_authored_guidance', 'compiler_scaffold')",
            name="ck_placement_decisions_transform_kind",
        ),
        sa.CheckConstraint(
            "disposition IN ('routed', 'blocked', 'unsupported', 'retired')",
            name="ck_placement_decisions_disposition",
        ),
        sa.CheckConstraint(
            "review_status IN ('approved', 'needs_review')",
            name="ck_placement_decisions_review_status",
        ),
        sa.UniqueConstraint(
            "rule_id", "version", name="uq_placement_decisions_rule_version"
        ),
    )
    op.create_index(
        "ix_placement_decisions_project_id",
        "placement_decisions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_placement_decisions_rule_id",
        "placement_decisions",
        ["rule_id"],
        unique=False,
    )

    op.create_table(
        "generated_spans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("build_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=True),
        sa.Column("placement_decision_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_path", sa.String(length=500), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("utf8_byte_start", sa.Integer(), nullable=False),
        sa.Column("utf8_byte_end", sa.Integer(), nullable=False),
        sa.Column("transform_kind", sa.String(length=40), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("line_start >= 1", name="ck_generated_spans_line_start"),
        sa.CheckConstraint(
            "line_end >= line_start", name="ck_generated_spans_line_order"
        ),
        sa.CheckConstraint(
            "utf8_byte_start >= 0", name="ck_generated_spans_byte_start"
        ),
        sa.CheckConstraint(
            "utf8_byte_end >= utf8_byte_start", name="ck_generated_spans_byte_order"
        ),
        sa.CheckConstraint(
            "transform_kind IN ('verbatim', 'reviewed_normalization', "
            "'reviewer_authored_guidance', 'compiler_scaffold')",
            name="ck_generated_spans_transform_kind",
        ),
        sa.CheckConstraint(
            "length(artifact_sha256) = 64",
            name="ck_generated_spans_artifact_sha256_length",
        ),
        sa.CheckConstraint(
            "length(text_sha256) = 64",
            name="ck_generated_spans_text_sha256_length",
        ),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["placement_decision_id"],
            ["placement_decisions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generated_spans_build_id", "generated_spans", ["build_id"], unique=False
    )
    op.create_index(
        "ix_generated_spans_rule_id", "generated_spans", ["rule_id"], unique=False
    )
    op.create_index(
        "ix_generated_spans_placement_decision_id",
        "generated_spans",
        ["placement_decision_id"],
        unique=False,
    )
    op.create_index(
        "ix_generated_spans_build_artifact",
        "generated_spans",
        ["build_id", "artifact_path"],
        unique=False,
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $aletheia_gate1_privileges$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.placement_decisions FROM anon;
                    REVOKE ALL PRIVILEGES ON TABLE public.generated_spans FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.placement_decisions FROM authenticated;
                    REVOKE ALL PRIVILEGES ON TABLE public.generated_spans FROM authenticated;
                END IF;
            END
            $aletheia_gate1_privileges$;
            """
        )


def downgrade() -> None:
    op.drop_index("ix_generated_spans_build_artifact", table_name="generated_spans")
    op.drop_index(
        "ix_generated_spans_placement_decision_id", table_name="generated_spans"
    )
    op.drop_index("ix_generated_spans_rule_id", table_name="generated_spans")
    op.drop_index("ix_generated_spans_build_id", table_name="generated_spans")
    op.drop_table("generated_spans")
    op.drop_index("ix_placement_decisions_rule_id", table_name="placement_decisions")
    op.drop_index("ix_placement_decisions_project_id", table_name="placement_decisions")
    op.drop_table("placement_decisions")

    with op.batch_alter_table("rules") as batch:
        batch.drop_constraint("ck_rules_provenance_kind", type_="check")
        batch.drop_column("provenance_metadata")
        batch.drop_column("provenance_kind")

    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("ck_documents_authority_status", type_="check")
        batch.drop_index("ix_documents_supersedes_document_id")
        batch.drop_constraint(
            "fk_documents_supersedes_document_id", type_="foreignkey"
        )
        batch.drop_column("version_label")
        batch.drop_column("authority_scopes")
        batch.drop_column("jurisdictions")
        batch.drop_column("supersedes_document_id")
        batch.drop_column("effective_at")
        batch.drop_column("authority_status")
        batch.drop_column("authority_owner")

    with op.batch_alter_table("projects") as batch:
        batch.drop_column("compilation_config")
        batch.drop_column("compiler_profile")
