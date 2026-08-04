"""Add authenticated workspace tenancy and durable operations.

Revision ID: 0002_tenancy_operations
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_tenancy_operations"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"
LOCAL_WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    partial_tables = {"user_accounts", "workspaces", "workspace_members"}.intersection(
        inspector.get_table_names()
    )
    if partial_tables:
        populated = any(
            bind.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")).first() is not None
            for table_name in partial_tables
        )
        if populated:
            raise RuntimeError(
                "Detected populated tenancy tables before tenancy migration; manual review is required"
            )
        for table_name in ("workspace_members", "workspaces", "user_accounts"):
            if table_name in partial_tables:
                op.drop_table(table_name)
        inspector = sa.inspect(bind)
    project_slug_unique = next(
        (
            item
            for item in inspector.get_unique_constraints("projects")
            if item.get("column_names") == ["slug"]
        ),
        None,
    )
    project_slug_constraint = (
        project_slug_unique["name"] or "uq_projects_slug" if project_slug_unique else None
    )
    project_slug_index = next(
        (
            item["name"]
            for item in inspector.get_indexes("projects")
            if item.get("unique") and item.get("column_names") == ["slug"]
        ),
        None,
    )
    build_hash_unique = next(
        (
            item
            for item in inspector.get_unique_constraints("builds")
            if item.get("column_names") == ["content_hash"]
        ),
        None,
    )
    build_hash_constraint = (
        build_hash_unique["name"] or "uq_builds_content_hash" if build_hash_unique else None
    )
    build_hash_index = next(
        (
            item["name"]
            for item in inspector.get_indexes("builds")
            if item.get("unique") and item.get("column_names") == ["content_hash"]
        ),
        None,
    )
    report_hash_unique = next(
        (
            item
            for item in inspector.get_unique_constraints("reports")
            if item.get("column_names") == ["content_hash"]
        ),
        None,
    )
    report_hash_constraint = (
        report_hash_unique["name"] or "uq_reports_content_hash"
        if report_hash_unique
        else None
    )
    report_hash_index = next(
        (
            item["name"]
            for item in inspector.get_indexes("reports")
            if item.get("unique") and item.get("column_names") == ["content_hash"]
        ),
        None,
    )
    legacy_project_id = bind.execute(
        sa.text("SELECT id FROM projects ORDER BY created_at LIMIT 1")
    ).scalar_one_or_none()
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_by_user_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])
    op.create_index("ix_workspaces_created_by_user_id", "workspaces", ["created_by_user_id"])
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_members_identity"
        ),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    if legacy_project_id is not None:
        op.execute(
            sa.text(
                "INSERT INTO user_accounts (id, email, created_at, updated_at) "
                "VALUES (:id, :email, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ).bindparams(id=LOCAL_USER_ID, email="local@aletheia.test")
        )
        op.execute(
            sa.text(
                "INSERT INTO workspaces "
                "(id, slug, name, created_by_user_id, created_at, updated_at) "
                "VALUES (:id, :slug, :name, :user_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ).bindparams(
                id=LOCAL_WORKSPACE_ID,
                slug="local-workspace",
                name="Local workspace",
                user_id=LOCAL_USER_ID,
            )
        )
        op.execute(
            sa.text(
                "INSERT INTO workspace_members "
                "(workspace_id, user_id, role, created_at, updated_at) "
                "VALUES (:workspace_id, :user_id, 'owner', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ).bindparams(workspace_id=LOCAL_WORKSPACE_ID, user_id=LOCAL_USER_ID)
        )

    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("workspace_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_projects_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if legacy_project_id is not None:
        op.execute(
            sa.text("UPDATE projects SET workspace_id = :workspace_id").bindparams(
                workspace_id=LOCAL_WORKSPACE_ID
            )
        )
    with op.batch_alter_table(
        "projects", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        batch.alter_column("workspace_id", existing_type=sa.String(36), nullable=False)
        if project_slug_constraint:
            batch.drop_constraint(project_slug_constraint, type_="unique")
        elif project_slug_index:
            batch.drop_index(project_slug_index)
        batch.create_unique_constraint(
            "uq_projects_workspace_slug", ["workspace_id", "slug"]
        )
        batch.create_index("ix_projects_workspace_id", ["workspace_id"])
        if project_slug_index == "ix_projects_slug":
            batch.create_index("ix_projects_slug", ["slug"], unique=False)

    with op.batch_alter_table(
        "builds", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        if build_hash_constraint:
            batch.drop_constraint(build_hash_constraint, type_="unique")
        elif build_hash_index:
            batch.drop_index(build_hash_index)
        batch.create_unique_constraint(
            "uq_builds_project_content_hash", ["project_id", "content_hash"]
        )

    with op.batch_alter_table(
        "reports", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        if report_hash_constraint:
            batch.drop_constraint(report_hash_constraint, type_="unique")
        elif report_hash_index:
            batch.drop_index(report_hash_index)
        batch.create_unique_constraint(
            "uq_reports_run_content_hash", ["run_id", "content_hash"]
        )

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("workspace_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("project_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("requested_by_user_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(255), nullable=True))
        batch.add_column(sa.Column("request_fingerprint", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3")
        )
        batch.create_foreign_key(
            "fk_jobs_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_jobs_project_id",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_jobs_requested_by_user_id",
            "user_accounts",
            ["requested_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if legacy_project_id is not None:
        op.execute(
            sa.text(
                "UPDATE jobs SET workspace_id = :workspace_id, project_id = :project_id, "
                "requested_by_user_id = :user_id, idempotency_key = id, "
                "request_fingerprint = :fingerprint"
            ).bindparams(
                workspace_id=LOCAL_WORKSPACE_ID,
                project_id=legacy_project_id,
                user_id=LOCAL_USER_ID,
                fingerprint="0" * 64,
            )
        )
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column("workspace_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("project_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("idempotency_key", existing_type=sa.String(255), nullable=False)
        batch.alter_column("request_fingerprint", existing_type=sa.String(64), nullable=False)
        batch.create_unique_constraint(
            "uq_jobs_workspace_project_kind_key",
            ["workspace_id", "project_id", "kind", "idempotency_key"],
        )
        batch.create_index("ix_jobs_workspace_id", ["workspace_id"])
        batch.create_index("ix_jobs_project_id", ["project_id"])
        batch.create_index("ix_jobs_requested_by_user_id", ["requested_by_user_id"])
    op.execute(
        sa.text(
            "UPDATE jobs SET status = 'queued', owner = NULL, lease_expiry = NULL "
            "WHERE status = 'running'"
        )
    )
    op.create_index(
        "uq_jobs_one_running_per_project",
        "jobs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
        sqlite_where=sa.text("status = 'running'"),
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $aletheia_privileges$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon';
                    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM authenticated';
                    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM authenticated';
                END IF;
            END
            $aletheia_privileges$;
            """
        )


def downgrade() -> None:
    op.drop_index("uq_jobs_one_running_per_project", table_name="jobs")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index("ix_jobs_requested_by_user_id")
        batch.drop_index("ix_jobs_workspace_id")
        batch.drop_index("ix_jobs_project_id")
        batch.drop_constraint("uq_jobs_workspace_project_kind_key", type_="unique")
        batch.drop_constraint("fk_jobs_requested_by_user_id", type_="foreignkey")
        batch.drop_constraint("fk_jobs_workspace_id", type_="foreignkey")
        batch.drop_constraint("fk_jobs_project_id", type_="foreignkey")
        batch.drop_column("max_attempts")
        batch.drop_column("request_fingerprint")
        batch.drop_column("idempotency_key")
        batch.drop_column("requested_by_user_id")
        batch.drop_column("workspace_id")
        batch.drop_column("project_id")
    with op.batch_alter_table("builds") as batch:
        batch.drop_constraint("uq_builds_project_content_hash", type_="unique")
        batch.create_unique_constraint("uq_builds_content_hash", ["content_hash"])
    with op.batch_alter_table("reports") as batch:
        batch.drop_constraint("uq_reports_run_content_hash", type_="unique")
        batch.create_unique_constraint("uq_reports_content_hash", ["content_hash"])
    with op.batch_alter_table("projects") as batch:
        batch.drop_index("ix_projects_workspace_id")
        batch.drop_constraint("uq_projects_workspace_slug", type_="unique")
        batch.create_unique_constraint("uq_projects_slug", ["slug"])
        batch.drop_constraint("fk_projects_workspace_id", type_="foreignkey")
        batch.drop_column("workspace_id")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_created_by_user_id", table_name="workspaces")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_table("user_accounts")
