from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import MetaData

from app.auth import LOCAL_USER_EMAIL, LOCAL_USER_ID, AuthIdentity, require_identity
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import (
    Finding,
    Job,
    Project,
    Rule,
    UserAccount,
    Workspace,
    WorkspaceMembership,
)
from app.operations import lock_operation_project
from app.services.guest_cleanup import cleanup_expired_guests
from app.services.review import resolve_finding, revise_rule
from app.tenancy import scoped_rule

API_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def _use_sqlite_migration_url(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    get_settings.cache_clear()


def test_empty_database_migrations_do_not_seed_global_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "empty.db"
    _use_sqlite_migration_url(monkeypatch, database)
    try:
        command.upgrade(_alembic_config(), "head")
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "0005_guest_access_waitlist",
            )
            assert connection.execute("SELECT count(*) FROM user_accounts").fetchone() == (0,)
            assert connection.execute("SELECT count(*) FROM waitlist_signups").fetchone() == (0,)
            assert connection.execute("SELECT count(*) FROM workspaces").fetchone() == (0,)
            assert connection.execute("SELECT count(*) FROM projects").fetchone() == (0,)
    finally:
        get_settings.cache_clear()


def test_migration_url_accepts_percent_encoded_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "encoded%40credential.db"
    _use_sqlite_migration_url(monkeypatch, database)
    try:
        command.upgrade(_alembic_config(), "head")
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "0005_guest_access_waitlist",
            )
    finally:
        get_settings.cache_clear()


def test_legacy_unnamed_unique_constraints_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id VARCHAR(36) PRIMARY KEY, slug VARCHAR(100) NOT NULL,
                name VARCHAR(200) NOT NULL, domain VARCHAR(80) NOT NULL,
                description TEXT NOT NULL, mode VARCHAR(40) NOT NULL,
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            );
            CREATE UNIQUE INDEX ix_projects_slug ON projects (slug);
            CREATE TABLE builds (
                id VARCHAR(36) PRIMARY KEY, project_id VARCHAR(36) NOT NULL,
                status VARCHAR(30) NOT NULL, input_manifest JSON NOT NULL,
                input_hash VARCHAR(64) NOT NULL, compiler_version VARCHAR(30) NOT NULL,
                artifacts JSON NOT NULL, source_map JSON NOT NULL, stats JSON NOT NULL,
                content_hash VARCHAR(64) NOT NULL UNIQUE, created_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE TABLE jobs (
                id VARCHAR(36) PRIMARY KEY, kind VARCHAR(40) NOT NULL,
                payload JSON NOT NULL, status VARCHAR(30) NOT NULL,
                progress INTEGER NOT NULL, resource_id VARCHAR(36), owner VARCHAR(120),
                lease_expiry DATETIME, attempt_count INTEGER NOT NULL,
                error_code VARCHAR(80), error_message TEXT, created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL, cancellable BOOLEAN NOT NULL
            );
            CREATE TABLE reports (
                id VARCHAR(36) PRIMARY KEY, run_id VARCHAR(36) NOT NULL,
                verdict VARCHAR(40) NOT NULL, evidence JSON NOT NULL,
                rendered_markdown TEXT NOT NULL,
                content_hash VARCHAR(64) NOT NULL UNIQUE,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY);
            INSERT INTO alembic_version VALUES ('0001_initial');
            INSERT INTO projects VALUES (
                'legacy-project', 'northstar-retail', 'Legacy', 'retail', '', 'demo',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            );
            """
        )
    _use_sqlite_migration_url(monkeypatch, database)
    try:
        command.upgrade(_alembic_config(), "head")
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT count(*) FROM workspaces").fetchone() == (1,)
            assert connection.execute(
                "SELECT workspace_id FROM projects WHERE id = 'legacy-project'"
            ).fetchone() == ("00000000-0000-0000-0000-000000000002",)
            job_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            assert {"workspace_id", "project_id", "idempotency_key"} <= job_columns
    finally:
        get_settings.cache_clear()


POSTGRES_RUNTIME_URL = os.getenv("TEST_DATABASE_URL")
POSTGRES_MIGRATION_URL = os.getenv("TEST_MIGRATION_DATABASE_URL")


@pytest.mark.skipif(
    not POSTGRES_RUNTIME_URL or not POSTGRES_MIGRATION_URL,
    reason="TEST_DATABASE_URL and TEST_MIGRATION_DATABASE_URL are required",
)
@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_empty_migration_and_operation_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert POSTGRES_RUNTIME_URL and POSTGRES_MIGRATION_URL
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", POSTGRES_RUNTIME_URL)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", POSTGRES_MIGRATION_URL)
    monkeypatch.setenv("DEMO_INLINE_JOBS", "false")
    get_settings.cache_clear()
    settings = get_settings()

    from sqlalchemy import create_engine

    sync_engine = create_engine(settings.migration_database_url)
    inspector = inspect(sync_engine)
    if "alembic_version" in inspector.get_table_names():
        command.downgrade(_alembic_config(), "base")
        with sync_engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    remaining = inspect(sync_engine).get_table_names()
    if remaining:
        metadata = MetaData()
        metadata.reflect(bind=sync_engine)
        pytest.fail(f"TEST_MIGRATION_DATABASE_URL must target an empty database: {remaining}")

    # Supabase exposes these roles through its Data API. Creating them in the
    # generic PostgreSQL CI service proves the migration's conditional REVOKEs
    # actually execute instead of silently skipping the hosted security path.
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                DO $aletheia_ci_roles$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                        CREATE ROLE anon NOLOGIN;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_roles WHERE rolname = 'authenticated'
                    ) THEN
                        CREATE ROLE authenticated NOLOGIN;
                    END IF;
                END
                $aletheia_ci_roles$;
                """
            )
        )

    command.upgrade(_alembic_config(), "head")
    with sync_engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS auth.users ("
                "id uuid PRIMARY KEY, "
                "is_anonymous boolean NOT NULL, "
                "created_at timestamptz NOT NULL"
                ")"
            )
        )
    with sync_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM user_accounts")) == 0
        assert connection.scalar(text("SELECT count(*) FROM workspaces")) == 0
        application_tables = [
            name
            for name in inspect(connection).get_table_names(schema="public")
            if name != "alembic_version"
        ]
        for role in ("anon", "authenticated"):
            for table_name in application_tables:
                relation = f"public.{table_name}"
                for privilege in (
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "TRUNCATE",
                    "REFERENCES",
                    "TRIGGER",
                ):
                    assert connection.scalar(
                        text(
                            "SELECT has_table_privilege(:role, :relation, :privilege)"
                        ),
                        {
                            "role": role,
                            "relation": relation,
                            "privilege": privilege,
                        },
                    ) is False

    with sync_engine.begin() as connection:
        connection.execute(text("CREATE TABLE public.aletheia_privilege_probe (id integer)"))
        for role in ("anon", "authenticated"):
            assert connection.scalar(
                text(
                    "SELECT has_table_privilege("
                    ":role, 'public.aletheia_privilege_probe', 'SELECT')"
                ),
                {"role": role},
            ) is False
        connection.execute(text("DROP TABLE public.aletheia_privilege_probe"))

    runtime_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    maker = async_sessionmaker(runtime_engine, expire_on_commit=False)

    async def override_session():  # type: ignore[no-untyped-def]
        async with maker() as session:
            yield session

    orphan_guest_id = "00000000-0000-0000-0000-000000000099"
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO auth.users (id, is_anonymous, created_at) "
                "VALUES (CAST(:id AS uuid), TRUE, :created_at)"
            ),
            {
                "id": orphan_guest_id,
                "created_at": datetime.now(UTC) - timedelta(days=31),
            },
        )
        await session.commit()
        cleanup = await cleanup_expired_guests(
            session,
            older_than_days=30,
            execute=True,
        )
        assert cleanup.guest_accounts == 0
        assert cleanup.auth_only_accounts == 1
        assert await session.scalar(
            text("SELECT count(*) FROM auth.users WHERE id::text = :id"),
            {"id": orphan_guest_id},
        ) == 0

    expired_auth_only_id = "00000000-0000-0000-0000-000000000096"
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO auth.users (id, is_anonymous, created_at) "
                "VALUES (CAST(:id AS uuid), TRUE, :created_at)"
            ),
            {
                "id": expired_auth_only_id,
                "created_at": datetime.now(UTC) - timedelta(days=8),
            },
        )
        await session.commit()

    async def override_expired_identity() -> AuthIdentity:
        return AuthIdentity(expired_auth_only_id, None, {"is_anonymous": True})

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_identity] = override_expired_identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            expired = await client.get("/api/v1/me")
        assert expired.status_code == 401
        assert expired.json()["code"] == "guest_session_expired"
    finally:
        app.dependency_overrides.pop(require_identity, None)
        app.dependency_overrides.pop(get_session, None)

    async with maker() as session:
        assert await session.get(UserAccount, expired_auth_only_id) is None
        assert await session.scalar(
            text("SELECT count(*) FROM auth.users WHERE id::text = :id"),
            {"id": expired_auth_only_id},
        ) == 1

    # A Supabase anonymous identity can be converted in place to a permanent
    # account. Hold that Auth-row update open while cleanup starts: cleanup must
    # wait for the authoritative conversion and then preserve the stale public
    # guest ledger and its workspace instead of deleting them in between its
    # Auth check and guarded Auth deletion.
    converted_guest_id = "00000000-0000-0000-0000-000000000098"
    converted_workspace_id = "00000000-0000-0000-0000-000000000097"
    old_guest_created_at = datetime.now(UTC) - timedelta(days=31)
    async with maker() as session:
        await session.execute(
            text(
                "INSERT INTO auth.users (id, is_anonymous, created_at) "
                "VALUES (CAST(:id AS uuid), TRUE, :created_at)"
            ),
            {"id": converted_guest_id, "created_at": old_guest_created_at},
        )
        session.add_all(
            [
                UserAccount(
                    id=converted_guest_id,
                    email=None,
                    is_anonymous=True,
                    created_at=old_guest_created_at,
                    updated_at=old_guest_created_at,
                ),
                Workspace(
                    id=converted_workspace_id,
                    slug="converted-guest-workspace",
                    name="Converted guest workspace",
                    created_by_user_id=converted_guest_id,
                    created_at=old_guest_created_at,
                    updated_at=old_guest_created_at,
                ),
                WorkspaceMembership(
                    workspace_id=converted_workspace_id,
                    user_id=converted_guest_id,
                    role="owner",
                    created_at=old_guest_created_at,
                    updated_at=old_guest_created_at,
                ),
            ]
        )
        await session.commit()

    async with maker() as conversion_session, maker() as cleanup_session:
        await conversion_session.execute(
            text(
                "UPDATE auth.users SET is_anonymous = FALSE "
                "WHERE id::text = :id"
            ),
            {"id": converted_guest_id},
        )
        preview = await asyncio.wait_for(
            cleanup_expired_guests(
                cleanup_session,
                older_than_days=30,
                execute=False,
            ),
            timeout=2,
        )
        assert preview.executed is False
        assert preview.guest_accounts == 1
        assert await cleanup_session.get(UserAccount, converted_guest_id) is not None
        cleanup_task = asyncio.create_task(
            cleanup_expired_guests(
                cleanup_session,
                older_than_days=30,
                execute=True,
            )
        )
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(cleanup_task), timeout=0.25)
            assert not cleanup_task.done()
            await conversion_session.commit()
            cleanup = await asyncio.wait_for(cleanup_task, timeout=2)
        finally:
            if not cleanup_task.done():
                cleanup_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await cleanup_task

    assert cleanup.guest_accounts == 0
    async with maker() as session:
        assert await session.get(UserAccount, converted_guest_id) is not None
        assert await session.get(Workspace, converted_workspace_id) is not None
        assert await session.scalar(
            text("SELECT is_anonymous FROM auth.users WHERE id::text = :id"),
            {"id": converted_guest_id},
        ) is False

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            bootstrap = await client.post("/api/v1/workspaces/bootstrap", json={})
            assert bootstrap.status_code == 200, bootstrap.text
            body = bootstrap.json()
            assert body["created"] is True
            project_id = body["project"]["id"]
            repeat = await client.post("/api/v1/workspaces/bootstrap", json={})
            assert repeat.status_code == 200
            assert repeat.json()["created"] is False
            assert repeat.json()["project"]["id"] == project_id

            async with maker() as session:
                findings = list(
                    (
                        await session.scalars(
                            select(Finding).where(
                                Finding.project_id == project_id,
                                Finding.severity == "critical",
                            )
                        )
                    ).all()
                )
                for finding in findings:
                    related = list(
                        (
                            await session.scalars(
                                select(Rule).where(Rule.id.in_(finding.related_rule_ids))
                            )
                        ).all()
                    )
                    winner = next(
                        rule
                        for rule in related
                        if not rule.stable_key.startswith("rule.legacy.")
                    )
                    loser = next(
                        rule
                        for rule in related
                        if rule.stable_key.startswith("rule.legacy.")
                    )
                    await resolve_finding(
                        session,
                        finding.id,
                        "resolved",
                        "Current policy is authoritative.",
                        winner_rule_id=winner.id,
                        loser_rule_id=loser.id,
                        authority="Refund Policy v3",
                        actor="postgres-test-user",
                    )
                threshold = await session.scalar(
                    select(Rule).where(
                        Rule.project_id == project_id,
                        Rule.stable_key == "rule.refund.approval_threshold",
                        Rule.status == "needs_review",
                    )
                )
                assert threshold
                await revise_rule(
                    session,
                    threshold.id,
                    expected_revision=threshold.revision,
                    changes={"reviewer_note": "Boundary reviewed."},
                    status="approved",
                )

            build = await client.post(
                f"/api/v1/projects/{project_id}/builds",
                headers={"Idempotency-Key": "pg-build"},
            )
            assert build.status_code == 202, build.text
            build_job = build.json()
            assert build_job["status"] == "queued"
            from app.worker import _process_owned_job

            async with maker() as session:
                queued_build = await session.get(Job, build_job["id"])
                assert queued_build is not None
                queued_build.status = "running"
                queued_build.owner = "postgres-test-worker"
                queued_build.attempt_count = 1
                await session.commit()
                await _process_owned_job(
                    session, queued_build, "postgres-test-worker"
                )
            build_poll = await client.get(f"/api/v1/jobs/{build_job['id']}")
            assert build_poll.status_code == 200
            build_job = build_poll.json()
            assert build_job["status"] == "succeeded"
            run = await client.post(
                f"/api/v1/projects/{project_id}/runs",
                headers={"Idempotency-Key": "pg-run"},
                json={"build_id": build_job["resource_id"]},
            )
            assert run.status_code == 202, run.text
            run_job = run.json()
            assert run_job["status"] == "queued"
            async with maker() as session:
                queued_run = await session.get(Job, run_job["id"])
                assert queued_run is not None
                queued_run.status = "running"
                queued_run.owner = "postgres-test-worker"
                queued_run.attempt_count = 1
                await session.commit()
                await _process_owned_job(
                    session, queued_run, "postgres-test-worker"
                )
            polled = await client.get(f"/api/v1/jobs/{run_job['id']}")
            assert polled.status_code == 200
            assert polled.json()["status"] == "succeeded"
            assert polled.json()["resource_id"] == run_job["id"]

            # A snapshot-consuming operation and every child-row mutation use
            # the same Project -> child lock order. Prove with two real
            # PostgreSQL sessions that the mutation cannot cross that fence.
            async with maker() as operation_session, maker() as mutation_session:
                operation_job = await operation_session.get(Job, run_job["id"])
                assert operation_job is not None
                await lock_operation_project(operation_session, operation_job)
                mutable_rule = await operation_session.scalar(
                    select(Rule).where(Rule.project_id == project_id).limit(1)
                )
                assert mutable_rule is not None
                mutation_acquired = asyncio.Event()

                async def lock_mutation() -> Rule:
                    resource = await scoped_rule(
                        mutation_session,
                        AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {}),
                        mutable_rule.id,
                        write=True,
                    )
                    mutation_acquired.set()
                    return resource

                mutation_task = asyncio.create_task(lock_mutation())
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(
                        asyncio.shield(mutation_acquired.wait()), timeout=0.25
                    )
                assert not mutation_task.done()
                await operation_session.commit()
                locked_rule = await asyncio.wait_for(mutation_task, timeout=2)
                assert locked_rule.id == mutable_rule.id
                await mutation_session.rollback()

            async with maker() as session:
                assert await session.get(Project, project_id)
    finally:
        app.dependency_overrides.pop(get_session, None)
        await runtime_engine.dispose()
        command.downgrade(_alembic_config(), "base")
        sync_engine.dispose()
        get_settings.cache_clear()
