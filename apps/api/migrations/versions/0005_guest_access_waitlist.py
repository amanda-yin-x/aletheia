"""Add guest-account metadata and privacy-minimal waitlist signups.

Revision ID: 0005_guest_access_waitlist
Revises: 0004_document_provenance
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_guest_access_waitlist"
down_revision = "0004_document_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    account_columns = {column["name"] for column in inspector.get_columns("user_accounts")}
    if "is_anonymous" not in account_columns:
        op.add_column(
            "user_accounts",
            sa.Column(
                "is_anonymous",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "guest_operation_count" not in account_columns:
        op.add_column(
            "user_accounts",
            sa.Column(
                "guest_operation_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    if "guest_mutation_count" not in account_columns:
        op.add_column(
            "user_accounts",
            sa.Column(
                "guest_mutation_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    if not inspector.has_table("waitlist_signups"):
        op.create_table(
            "waitlist_signups",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=False),
            sa.Column("consent_version", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user_accounts.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_waitlist_signups_email"),
            sa.UniqueConstraint("user_id", name="uq_waitlist_signups_user_id"),
        )
        op.create_index(
            "ix_waitlist_signups_user_id",
            "waitlist_signups",
            ["user_id"],
            unique=False,
        )

    report_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("reports")
            if foreign_key.get("constrained_columns") == ["run_id"]
        ),
        None,
    )
    if report_foreign_key and (
        report_foreign_key.get("options") or {}
    ).get("ondelete", "").upper() != "CASCADE":
        constraint_name = report_foreign_key.get("name") or "fk_reports_run_id_runs"
        with op.batch_alter_table(
            "reports",
            naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"},
        ) as batch:
            batch.drop_constraint(constraint_name, type_="foreignkey")
            batch.create_foreign_key(
                "fk_reports_run_id_runs",
                "runs",
                ["run_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $aletheia_waitlist_privileges$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.waitlist_signups FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.waitlist_signups FROM authenticated;
                END IF;
            END
            $aletheia_waitlist_privileges$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("waitlist_signups"):
        op.drop_index("ix_waitlist_signups_user_id", table_name="waitlist_signups")
        op.drop_table("waitlist_signups")
    report_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("reports")
            if foreign_key.get("constrained_columns") == ["run_id"]
        ),
        None,
    )
    if report_foreign_key and (
        report_foreign_key.get("options") or {}
    ).get("ondelete", "").upper() == "CASCADE":
        constraint_name = report_foreign_key.get("name") or "fk_reports_run_id_runs"
        with op.batch_alter_table(
            "reports",
            naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"},
        ) as batch:
            batch.drop_constraint(constraint_name, type_="foreignkey")
            batch.create_foreign_key(
                "fk_reports_run_id_runs",
                "runs",
                ["run_id"],
                ["id"],
            )
    account_columns = {column["name"] for column in inspector.get_columns("user_accounts")}
    if "guest_mutation_count" in account_columns:
        op.drop_column("user_accounts", "guest_mutation_count")
    if "guest_operation_count" in account_columns:
        op.drop_column("user_accounts", "guest_operation_count")
    if "is_anonymous" in account_columns:
        op.drop_column("user_accounts", "is_anonymous")
