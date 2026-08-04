from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import auth, worker
from app import main as app_main
from app.api import routes as api_routes
from app.auth import LOCAL_USER_EMAIL, LOCAL_USER_ID, AuthIdentity, require_identity
from app.config import Settings, get_settings
from app.db import get_session
from app.main import app
from app.models import (
    Build,
    Document,
    Finding,
    Job,
    Project,
    Report,
    Rule,
    Run,
    UserAccount,
    WaitlistSignup,
    Workspace,
    WorkspaceMembership,
)
from app.operations import create_operation, execute_inline
from app.services.canonical import content_hash
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.guest_cleanup import cleanup_expired_guests
from app.services.reporting import create_report
from app.services.review import resolve_finding, revise_rule
from app.services.runner import run_comparison
from app.services.seed import seed_demo
from app.tenancy import scoped_build, scoped_document, scoped_job, scoped_project
from app.worker import recover_expired_leases


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://user:pass@db.example:5432/aletheia?ssl=require",
        "migration_database_url": "postgresql+psycopg://user:pass@db.example:5432/aletheia?sslmode=require",
        "supabase_issuer": "https://project.supabase.co/auth/v1",
        "supabase_jwks_url": "https://project.supabase.co/auth/v1/.well-known/jwks.json",
        "supabase_audience": "authenticated",
        "api_origin_token": "origin-secret-with-at-least-32-characters",
        "web_origin": "https://app.example.com",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_settings_default_fail_closed_and_redact_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings.model_fields["environment"].default == "production"
    for name in (
        "ENVIRONMENT",
        "DATABASE_URL",
        "MIGRATION_DATABASE_URL",
        "SUPABASE_ISSUER",
        "SUPABASE_JWKS_URL",
        "SUPABASE_AUDIENCE",
        "API_ORIGIN_TOKEN",
        "WEB_ORIGIN",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Hosted mode requires"):
        Settings(_env_file=None)

    database_password = "FAKE_DATABASE_PASSWORD_FOR_REDACTION"
    migration_password = "FAKE_MIGRATION_PASSWORD_FOR_REDACTION"
    origin_secret = "FAKE_ORIGIN_SECRET_THAT_IS_LONGER_THAN_32_CHARS"
    model_key = "FAKE_MODEL_PROVIDER_KEY_FOR_REDACTION"
    settings = _production_settings(
        database_url=(
            f"postgresql+asyncpg://user:{database_password}@db.example:5432/aletheia?ssl=require"
        ),
        migration_database_url=(
            "postgresql+psycopg://user:"
            f"{migration_password}@db.example:5432/aletheia?sslmode=require"
        ),
        api_origin_token=origin_secret,
        openai_api_key=model_key,
    )
    rendered_settings = repr(settings)
    for secret in (database_password, migration_password, origin_secret, model_key):
        assert secret not in rendered_settings

    short_origin_secret = "FAKE_SHORT_ORIGIN_SECRET"
    with pytest.raises(ValueError) as invalid:
        _production_settings(
            database_url=(
                "postgresql+asyncpg://user:"
                f"{database_password}@db.example:5432/aletheia?ssl=require"
            ),
            migration_database_url=(
                "postgresql+psycopg://user:"
                f"{migration_password}@db.example:5432/aletheia?sslmode=require"
            ),
            api_origin_token=short_origin_secret,
            openai_api_key=model_key,
        )
    rendered_error = str(invalid.value)
    for secret in (
        database_password,
        migration_password,
        short_origin_secret,
        model_key,
    ):
        assert secret not in rendered_error


@pytest.mark.asyncio
async def test_production_auth_never_uses_local_identity_without_credentials() -> None:
    settings = _production_settings()
    assert settings.local_identity_enabled is False
    with pytest.raises(ServiceError) as missing_identity:
        await auth.require_identity(credentials=None, settings=settings)
    assert missing_identity.value.status_code == 401
    with pytest.raises(ServiceError) as missing_origin:
        await auth.require_origin_token(
            x_aletheia_origin_token=None,
            settings=settings,
        )
    assert missing_origin.value.status_code == 403


@pytest.mark.asyncio
async def test_hosted_boundary_rejects_upload_before_reading_multipart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _production_settings()
    monkeypatch.setattr(app_main, "settings", settings)

    class UnreadOversizedBody(httpx.AsyncByteStream):
        reads = 0

        async def __aiter__(self):  # type: ignore[no-untyped-def]
            self.reads += 1
            yield b"x" * (settings.upload_max_bytes + 1)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example.com"
    ) as client:
        without_boundary = UnreadOversizedBody()
        blocked_origin = await client.post(
            "/api/v1/projects/project-id/documents",
            headers={"Content-Type": "multipart/form-data"},
            content=without_boundary,
        )
        assert blocked_origin.status_code == 403
        assert blocked_origin.json()["code"] == "origin_not_allowed"
        assert without_boundary.reads == 0

        without_identity = UnreadOversizedBody()
        blocked_identity = await client.post(
            "/api/v1/projects/project-id/documents",
            headers={
                "Content-Type": "multipart/form-data",
                "X-Aletheia-Origin-Token": settings.api_origin_token,
            },
            content=without_identity,
        )
        assert blocked_identity.status_code == 401
        assert blocked_identity.json()["code"] == "authentication_required"
        assert without_identity.reads == 0

        hosted_upload = UnreadOversizedBody()
        disabled = await client.post(
            "/api/v1/projects/project-id/documents",
            headers={
                "Authorization": "Bearer structurally-present-token",
                "Content-Type": "multipart/form-data",
                "X-Aletheia-Origin-Token": settings.api_origin_token,
            },
            content=hosted_upload,
        )
        assert disabled.status_code == 403
        assert disabled.json()["code"] == "uploads_disabled_in_hosted_workspace"
        assert hosted_upload.reads == 0


@pytest.mark.asyncio
async def test_hosted_boundary_caps_declared_and_chunked_mutation_bodies(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
) -> None:
    settings = _production_settings(api_max_body_bytes=4096)
    monkeypatch.setattr(app_main, "settings", settings)

    class OversizedBody(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.reads = 0

        async def __aiter__(self):  # type: ignore[no-untyped-def]
            self.reads += 1
            yield b"x" * (settings.api_max_body_bytes + 1)

    boundary_headers = {
        "Authorization": "Bearer structurally-present-token",
        "Content-Type": "application/json",
        "X-Aletheia-Origin-Token": settings.api_origin_token,
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example.com"
    ) as client:
        declared_body = OversizedBody()
        declared = await client.post(
            "/api/v1/waitlist",
            headers={
                **boundary_headers,
                "Content-Length": str(settings.api_max_body_bytes + 1),
            },
            content=declared_body,
        )
        assert declared.status_code == 413
        assert declared.json()["code"] == "request_body_too_large"
        assert declared_body.reads == 0

        chunked_body = OversizedBody()
        chunked = await client.post(
            "/api/v1/waitlist",
            headers=boundary_headers,
            content=chunked_body,
        )
        assert chunked.status_code == 413
        assert chunked.json()["code"] == "request_body_too_large"
        assert chunked_body.reads == 1

        identity = AuthIdentity(
            "bounded-body-user",
            "bounded-body@example.com",
            {},
        )

        async def override_identity() -> AuthIdentity:
            return identity

        async def override_session():  # type: ignore[no-untyped-def]
            yield session

        app.dependency_overrides[require_identity] = override_identity
        app.dependency_overrides[get_session] = override_session
        try:
            accepted = await client.post(
                "/api/v1/waitlist",
                headers=boundary_headers,
                json={"email": identity.email},
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json() == {"joined": True}
            stored = await session.scalar(
                select(WaitlistSignup).where(WaitlistSignup.user_id == identity.subject)
            )
            assert stored is not None
            assert stored.email == identity.email
        finally:
            app.dependency_overrides.pop(get_session, None)
            app.dependency_overrides.pop(require_identity, None)


def test_production_configuration_and_jwt_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="Hosted mode requires"):
        Settings(environment="production")
    with pytest.raises(ValueError, match="Production requires PostgreSQL"):
        _production_settings(database_url="sqlite+aiosqlite:///unsafe.db")

    settings = _production_settings()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    monkeypatch.setattr(
        auth,
        "_jwks_client",
        lambda _url: SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=public_key)
        ),
    )
    now = datetime.now(UTC)
    claims = {
        "iss": settings.supabase_issuer,
        "aud": settings.supabase_audience,
        "sub": "93cce26b-27ef-4870-9dfc-58f61fb9dc4c",
        "role": "authenticated",
        "email": "owner@example.com",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})
    decoded = auth._decode_token(token, settings)
    assert decoded["sub"] == claims["sub"]

    anonymous = jwt.encode(
        {**claims, "email": None, "is_anonymous": True},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    anonymous_claims = auth._decode_token(anonymous, settings)
    assert anonymous_claims["is_anonymous"] is True

    invalid = jwt.encode(
        {**claims, "aud": "wrong"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    with pytest.raises(ServiceError) as error:
        auth._decode_token(invalid, settings)
    assert error.value.code == "authentication_required"
    assert error.value.status_code == 401

    wrong_role = jwt.encode(
        {**claims, "role": "anon"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    with pytest.raises(ServiceError) as wrong_role_error:
        auth._decode_token(wrong_role, settings)
    assert wrong_role_error.value.status_code == 401


async def _prepare_buildable_project(session: AsyncSession, project: Project) -> None:
    findings = list(
        (
            await session.scalars(
                select(Finding).where(
                    Finding.project_id == project.id,
                    Finding.severity == "critical",
                )
            )
        ).all()
    )
    for finding in findings:
        related = list(
            (await session.scalars(select(Rule).where(Rule.id.in_(finding.related_rule_ids)))).all()
        )
        winner = next(rule for rule in related if not rule.stable_key.startswith("rule.legacy."))
        loser = next(rule for rule in related if rule.stable_key.startswith("rule.legacy."))
        await resolve_finding(
            session,
            finding.id,
            "resolved",
            "Current policy is authoritative.",
            winner_rule_id=winner.id,
            loser_rule_id=loser.id,
            authority="Refund Policy v3",
            actor=LOCAL_USER_ID,
        )
    threshold = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
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


@pytest.mark.asyncio
async def test_bootstrap_operation_contract_idempotency_and_reset(
    session: AsyncSession,
) -> None:
    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            bootstrap = await client.post("/api/v1/workspaces/bootstrap", json={})
            assert bootstrap.status_code == 200
            first = bootstrap.json()
            assert first["created"] is False
            project_id = first["project"]["id"]
            project = await session.get(Project, project_id)
            assert project
            await _prepare_buildable_project(session, project)

            build_response = await client.post(
                f"/api/v1/projects/{project.id}/builds",
                headers={"Idempotency-Key": "compile-release-1"},
            )
            assert build_response.status_code == 202
            build_operation = build_response.json()
            assert build_response.headers["location"] == (f"/api/v1/jobs/{build_operation['id']}")
            assert build_operation["status"] == "succeeded"
            assert build_operation["resource_type"] == "build"

            duplicate = await client.post(
                f"/api/v1/projects/{project.id}/builds",
                headers={"Idempotency-Key": "compile-release-1"},
            )
            assert duplicate.json()["id"] == build_operation["id"]

            run_response = await client.post(
                f"/api/v1/projects/{project.id}/runs",
                headers={"Idempotency-Key": "run-release-1"},
                json={"build_id": build_operation["resource_id"]},
            )
            assert run_response.status_code == 202
            run_operation = run_response.json()
            assert run_operation["status"] == "succeeded"
            assert run_operation["resource_type"] == "run"
            assert run_operation["resource_id"] == run_operation["id"]

            polled = await client.get(f"/api/v1/jobs/{run_operation['id']}")
            assert polled.status_code == 200
            assert polled.json() == run_operation

            with pytest.raises(ServiceError) as conflict:
                await create_operation(
                    session,
                    identity=AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {}),
                    project=project,
                    kind="compile",
                    payload={"project_id": project.id, "different": True},
                    idempotency_key="compile-release-1",
                )
            assert conflict.value.code == "idempotency_conflict"

            reset = await client.post(f"/api/v1/projects/{project.id}/reset")
            assert reset.status_code == 200
            assert reset.json()["id"] == project.id
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_bootstrap_never_seeds_a_shared_viewer_workspace(
    session: AsyncSession,
) -> None:
    shared = await session.scalar(
        select(Workspace).where(Workspace.created_by_user_id == LOCAL_USER_ID)
    )
    assert shared
    viewer = AuthIdentity("viewer-user", "viewer@example.com", {})
    session.add(UserAccount(id=viewer.subject, email=viewer.email))
    session.add(
        WorkspaceMembership(
            workspace_id=shared.id,
            user_id=viewer.subject,
            role="viewer",
        )
    )
    await session.commit()

    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    async def override_identity() -> AuthIdentity:
        return viewer

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_identity] = override_identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/workspaces/bootstrap", json={})
        assert response.status_code == 200
        payload = response.json()
        assert payload["created"] is True
        assert payload["workspace"]["id"] != shared.id
        personal = await session.get(Workspace, payload["workspace"]["id"])
        assert personal and personal.created_by_user_id == viewer.subject
    finally:
        app.dependency_overrides.pop(require_identity, None)
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_waitlist_is_normalized_private_and_idempotent(
    session: AsyncSession,
) -> None:
    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            joined = await client.post(
                "/api/v1/waitlist", json={"email": "  Founder@Example.COM  "}
            )
            repeated = await client.post(
                "/api/v1/waitlist", json={"email": "founder@example.com"}
            )
            changed = await client.post(
                "/api/v1/waitlist", json={"email": "another@example.com"}
            )
            invalid = await client.post(
                "/api/v1/waitlist", json={"email": "not-an-email"}
            )

        assert joined.status_code == 200
        assert repeated.json() == {"joined": True}
        assert changed.json() == {"joined": True}
        assert invalid.status_code == 422
        signups = list((await session.scalars(select(WaitlistSignup))).all())
        assert len(signups) == 1
        assert signups[0].email == "founder@example.com"
        assert signups[0].user_id == LOCAL_USER_ID
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_guest_operation_quota_and_reset_boundary(
    session: AsyncSession,
) -> None:
    guest = AuthIdentity("guest-user", None, {"is_anonymous": True})
    guest_account = UserAccount(
        id=guest.subject,
        email=None,
        is_anonymous=True,
        guest_operation_count=get_settings().guest_max_operations,
        guest_mutation_count=get_settings().guest_max_mutations,
    )
    guest_workspace = Workspace(
        id="guest-workspace",
        slug="guest-workspace",
        name="Guest workspace",
        created_by_user_id=guest.subject,
    )
    session.add_all(
        [
            guest_account,
            guest_workspace,
            WorkspaceMembership(
                workspace_id=guest_workspace.id,
                user_id=guest.subject,
                role="owner",
            ),
        ]
    )
    await session.commit()
    guest_project = await seed_demo(session, workspace_id=guest_workspace.id)
    guest_rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == guest_project.id,
            Rule.status != "superseded",
        )
    )
    assert guest_rule is not None

    with pytest.raises(ServiceError) as limited:
        await create_operation(
            session,
            identity=guest,
            project=guest_project,
            kind="compile",
            payload={"project_id": guest_project.id},
            idempotency_key="over-quota",
        )
    assert limited.value.code == "guest_operation_limit_reached"
    assert limited.value.status_code == 429

    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    async def override_identity() -> AuthIdentity:
        return guest

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_identity] = override_identity
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            denied = await client.post(f"/api/v1/projects/{guest_project.id}/reset")
            hidden = await client.post(
                "/api/v1/projects/00000000-0000-0000-0000-999999999999/reset"
            )
            mutation_limited = await client.post(
                f"/api/v1/rules/{guest_rule.id}/approve",
                json={"expected_revision": guest_rule.revision},
            )
        assert denied.status_code == 403
        assert denied.json()["code"] == "guest_reset_disabled"
        assert hidden.status_code == 404
        assert mutation_limited.status_code == 429
        assert mutation_limited.json()["code"] == "guest_mutation_limit_reached"
    finally:
        app.dependency_overrides.pop(require_identity, None)
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_guest_cleanup_dry_run_and_workspace_cascade(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    old_guest = UserAccount(
        id="expired-guest",
        email=None,
        is_anonymous=True,
        created_at=now - timedelta(days=31),
        updated_at=now - timedelta(days=31),
    )
    old_workspace = Workspace(
        id="expired-guest-workspace",
        slug="expired-guest-workspace",
        name="Expired guest workspace",
        created_by_user_id=old_guest.id,
        created_at=now - timedelta(days=31),
        updated_at=now - timedelta(days=31),
    )
    signup = WaitlistSignup(
        id="expired-guest-waitlist",
        user_id=old_guest.id,
        email="keep-consent@example.com",
        source="landing",
        consent_version="2026-08-04",
        created_at=now - timedelta(days=31),
    )
    session.add_all(
        [
            old_guest,
            old_workspace,
            WorkspaceMembership(
                workspace_id=old_workspace.id,
                user_id=old_guest.id,
                role="owner",
            ),
            signup,
        ]
    )
    await session.commit()
    old_project = await seed_demo(session, workspace_id=old_workspace.id)
    await _prepare_buildable_project(session, old_project)
    old_build = await compile_project(session, old_project.id)
    old_run = await run_comparison(session, old_project.id, old_build.id)
    old_report = await create_report(session, old_run.id)
    old_guest_id = old_guest.id
    old_workspace_id = old_workspace.id
    old_project_id = old_project.id
    signup_id = signup.id
    old_run_id = old_run.id
    old_report_id = old_report.id

    preview = await cleanup_expired_guests(
        session,
        older_than_days=30,
        execute=False,
        now=now,
    )
    assert preview.guest_accounts == 1
    assert preview.auth_only_accounts == 0
    assert preview.workspaces == 1
    assert preview.projects == 1
    assert preview.linked_waitlist_signups == 1
    assert await session.get(Project, old_project_id) is not None

    applied = await cleanup_expired_guests(
        session,
        older_than_days=30,
        execute=True,
        now=now,
    )
    assert applied.executed is True
    session.expire_all()
    assert await session.get(UserAccount, old_guest_id) is None
    assert await session.get(Workspace, old_workspace_id) is None
    assert await session.get(Project, old_project_id) is None
    assert await session.get(Run, old_run_id) is None
    assert await session.get(Report, old_report_id) is None
    preserved_signup = await session.get(WaitlistSignup, signup_id)
    assert preserved_signup is not None
    assert preserved_signup.user_id is None
    assert preserved_signup.email == "keep-consent@example.com"

    repeated = await cleanup_expired_guests(
        session,
        older_than_days=30,
        execute=True,
        now=now,
    )
    assert repeated.executed is True
    assert repeated.guest_accounts == 0
    assert repeated.auth_only_accounts == 0
    assert repeated.workspaces == 0
    assert repeated.projects == 0


@pytest.mark.asyncio
async def test_tenant_scopes_and_cross_project_builds_return_not_found(
    session: AsyncSession,
) -> None:
    local_project = await session.scalar(
        select(Project).where(Project.workspace_id != "other-workspace")
    )
    assert local_project
    other_identity = AuthIdentity("other-user", "other@example.com", {})
    session.add(UserAccount(id=other_identity.subject, email=other_identity.email))
    session.add(
        Workspace(
            id="other-workspace",
            slug="other-workspace",
            name="Other workspace",
            created_by_user_id=other_identity.subject,
        )
    )
    session.add(
        WorkspaceMembership(
            workspace_id="other-workspace", user_id=other_identity.subject, role="owner"
        )
    )
    other_project = Project(
        id="other-project",
        workspace_id="other-workspace",
        slug="northstar-retail",
        name="Other project",
        domain="retail",
        description="Isolated",
        mode="demo",
    )
    session.add(other_project)
    other_document = Document(
        id="other-document",
        project_id=other_project.id,
        kind="policy",
        name="other.md",
        version=1,
        original_sha256="0" * 64,
        normalized_sha256="1" * 64,
        normalized_text="private",
        mime_type="text/markdown",
        line_count=1,
        token_estimate=1,
        origin={},
    )
    session.add(other_document)
    other_build = Build(
        id="other-build",
        project_id=other_project.id,
        status="succeeded",
        input_manifest={},
        input_hash="1" * 64,
        compiler_version="test",
        artifacts={},
        source_map={},
        stats={},
        content_hash="2" * 64,
    )
    session.add(other_build)
    other_job = Job(
        id="other-job",
        workspace_id="other-workspace",
        project_id=other_project.id,
        requested_by_user_id=other_identity.subject,
        kind="compile",
        payload={"project_id": other_project.id},
        idempotency_key="other",
        request_fingerprint="3" * 64,
    )
    session.add(other_job)
    await session.commit()

    local = AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {})
    for loader, resource_id in (
        (scoped_project, other_project.id),
        (scoped_document, other_document.id),
        (scoped_build, other_build.id),
        (scoped_job, other_job.id),
    ):
        with pytest.raises(ServiceError) as missing:
            await loader(session, local, resource_id)
        assert missing.value.status_code == 404

    with pytest.raises(ServiceError) as cross_project:
        await run_comparison(session, local_project.id, other_build.id)
    assert cross_project.value.code == "build_not_found"
    assert cross_project.value.status_code == 404

    local_build = Build(
        id="local-build",
        project_id=local_project.id,
        status="succeeded",
        input_manifest={},
        input_hash="8" * 64,
        compiler_version="test",
        artifacts={},
        source_map={},
        stats={},
        content_hash="2" * 64,
    )
    local_run = Run(
        id="local-run",
        project_id=local_project.id,
        build_id=local_build.id,
        requested_arms=[],
        adapter="fixture",
        dataset_manifest={},
        status="succeeded",
        metrics={},
    )
    other_run = Run(
        id="other-run",
        project_id=other_project.id,
        build_id=other_build.id,
        requested_arms=[],
        adapter="fixture",
        dataset_manifest={},
        status="succeeded",
        metrics={},
    )
    session.add_all([local_build, local_run, other_run])
    await session.flush()
    session.add_all(
        [
            Report(
                run_id=local_run.id,
                verdict="Ready",
                evidence={},
                rendered_markdown="same",
                content_hash="9" * 64,
            ),
            Report(
                run_id=other_run.id,
                verdict="Ready",
                evidence={},
                rendered_markdown="same",
                content_hash="9" * 64,
            ),
        ]
    )
    await session.commit()
    assert (
        len(
            list(
                (await session.scalars(select(Report).where(Report.content_hash == "9" * 64))).all()
            )
        )
        == 2
    )


@pytest.mark.asyncio
async def test_cross_project_idempotency_and_reset_isolation(session: AsyncSession) -> None:
    northstar = await session.scalar(select(Project).where(Project.slug == "northstar-retail"))
    assert northstar
    second = Project(
        workspace_id=northstar.workspace_id,
        slug="second-project",
        name="Second",
        domain="test",
        description="",
        mode="local",
    )
    session.add(second)
    await session.flush()
    identity = AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {})
    first_job, _ = await create_operation(
        session,
        identity=identity,
        project=northstar,
        kind="analyze",
        payload={"project_id": northstar.id},
        idempotency_key="shared-key",
    )
    second_job, _ = await create_operation(
        session,
        identity=identity,
        project=second,
        kind="analyze",
        payload={"project_id": second.id},
        idempotency_key="shared-key",
    )
    assert first_job.id != second_job.id
    assert first_job.request_fingerprint != second_job.request_fingerprint
    reset = await seed_demo(session, workspace_id=northstar.workspace_id, reset=True)
    assert reset.id == northstar.id
    assert await session.get(Job, first_job.id) is None
    assert await session.get(Job, second_job.id) is not None


@pytest.mark.asyncio
async def test_workspace_reset_locks_only_the_authenticated_northstar_project(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_project = await session.scalar(select(Project).where(Project.slug == "northstar-retail"))
    assert local_project
    local_project_id = local_project.id
    local_workspace_id = local_project.workspace_id

    other_identity = AuthIdentity("reset-other-user", "reset-other@example.com", {})
    other_workspace = Workspace(
        id="reset-other-workspace",
        slug="reset-other-workspace",
        name="Reset other workspace",
        created_by_user_id=other_identity.subject,
    )
    session.add_all(
        [
            UserAccount(id=other_identity.subject, email=other_identity.email),
            other_workspace,
            WorkspaceMembership(
                workspace_id=other_workspace.id,
                user_id=other_identity.subject,
                role="owner",
            ),
        ]
    )
    await session.commit()
    other_project = await seed_demo(session, workspace_id=other_workspace.id)
    other_project_id = other_project.id
    other_document_ids = set(
        (
            await session.scalars(
                select(Document.id).where(Document.project_id == other_project_id)
            )
        ).all()
    )
    assert other_document_ids

    locked_projects: list[tuple[str, bool]] = []
    original_scoped_project = api_routes.scoped_project

    async def tracked_scoped_project(
        scoped_session: AsyncSession,
        identity: AuthIdentity,
        project_id: str,
        *,
        write: bool = False,
    ) -> Project:
        locked_projects.append((project_id, write))
        return await original_scoped_project(scoped_session, identity, project_id, write=write)

    monkeypatch.setattr(api_routes, "scoped_project", tracked_scoped_project)

    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            reset = await client.post(f"/api/v1/workspaces/{local_workspace_id}/reset")
            assert reset.status_code == 200
            assert reset.json()["id"] == local_project_id
            assert locked_projects == [(local_project_id, True)]

            forbidden = await client.post(f"/api/v1/workspaces/{other_workspace.id}/reset")
            assert forbidden.status_code == 404
            assert locked_projects == [(local_project_id, True)]
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert await session.get(Project, other_project_id) is not None
    preserved_document_ids = set(
        (
            await session.scalars(
                select(Document.id).where(Document.project_id == other_project_id)
            )
        ).all()
    )
    assert preserved_document_ids == other_document_ids


@pytest.mark.asyncio
async def test_expired_leases_recover_or_dead_letter(session: AsyncSession) -> None:
    first_project = await session.scalar(select(Project).limit(1))
    assert first_project
    second_project = Project(
        workspace_id=first_project.workspace_id,
        slug="lease-test",
        name="Lease test",
        domain="test",
        description="",
        mode="local",
    )
    session.add(second_project)
    await session.flush()
    expired = datetime.now(UTC) - timedelta(minutes=1)
    recoverable = Job(
        workspace_id=first_project.workspace_id,
        project_id=first_project.id,
        kind="analyze",
        payload={"project_id": first_project.id},
        idempotency_key="recoverable",
        request_fingerprint="4" * 64,
        status="running",
        owner="gone",
        lease_expiry=expired,
        attempt_count=1,
        max_attempts=3,
    )
    exhausted = Job(
        workspace_id=first_project.workspace_id,
        project_id=second_project.id,
        kind="analyze",
        payload={"project_id": second_project.id},
        idempotency_key="exhausted",
        request_fingerprint="5" * 64,
        status="running",
        owner="gone",
        lease_expiry=expired,
        attempt_count=3,
        max_attempts=3,
    )
    session.add_all([recoverable, exhausted])
    await session.commit()
    assert await recover_expired_leases(session) == (1, 1)
    await session.refresh(recoverable)
    await session.refresh(exhausted)
    assert recoverable.status == "queued" and recoverable.owner is None
    assert exhausted.status == "dead_lettered"
    assert exhausted.error_code == "retry_limit_exceeded"


@pytest.mark.asyncio
async def test_active_inline_idempotency_normalizes_whitespace_replay(
    session: AsyncSession,
) -> None:
    project = await session.scalar(select(Project).limit(1))
    assert project
    request_payload = {"project_id": project.id, "extractor": "fixture"}
    active = Job(
        workspace_id=project.workspace_id,
        project_id=project.id,
        requested_by_user_id=LOCAL_USER_ID,
        kind="analyze",
        payload={
            **request_payload,
            "input_fingerprint": content_hash({"project_id": project.id}),
        },
        idempotency_key="active-inline-replay",
        request_fingerprint=content_hash(
            {
                "workspace_id": project.workspace_id,
                "project_id": project.id,
                "kind": "analyze",
                "payload": request_payload,
            }
        ),
        status="running",
        progress=40,
        resource_id=project.id,
        owner="inline-regression",
        lease_expiry=datetime.now(UTC) + timedelta(minutes=5),
        attempt_count=1,
    )
    session.add(active)
    await session.commit()

    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            replay = await client.post(
                f"/api/v1/projects/{project.id}/analysis-jobs",
                headers={"Idempotency-Key": "  active-inline-replay  "},
            )
        assert replay.status_code == 202
        assert replay.headers["location"] == f"/api/v1/jobs/{active.id}"
        operation = replay.json()
        assert operation["id"] == active.id
        assert operation["resource_id"] == project.id
        assert operation["status"] == "running"
    finally:
        app.dependency_overrides.pop(get_session, None)

    matching = list(
        (
            await session.scalars(
                select(Job).where(
                    Job.project_id == project.id,
                    Job.idempotency_key == "active-inline-replay",
                )
            )
        ).all()
    )
    assert [job.id for job in matching] == [active.id]


@pytest.mark.asyncio
async def test_inline_project_concurrency_never_leaves_queued_work(
    session: AsyncSession,
) -> None:
    project = await session.scalar(select(Project).limit(1))
    assert project
    active = Job(
        workspace_id=project.workspace_id,
        project_id=project.id,
        kind="analyze",
        payload={"project_id": project.id},
        idempotency_key="active-inline",
        request_fingerprint="6" * 64,
        status="running",
        attempt_count=1,
    )
    loser = Job(
        workspace_id=project.workspace_id,
        project_id=project.id,
        kind="analyze",
        payload={"project_id": project.id},
        idempotency_key="loser-inline",
        request_fingerprint="7" * 64,
        status="queued",
    )
    session.add_all([active, loser])
    await session.commit()

    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            blocked = await client.post(
                f"/api/v1/projects/{project.id}/analysis-jobs",
                headers={"Idempotency-Key": "blocked-inline"},
            )
            assert blocked.status_code == 409
            assert blocked.json()["code"] == "project_operation_in_progress"
    finally:
        app.dependency_overrides.pop(get_session, None)
    completed = await execute_inline(session, loser.id)
    assert completed.status == "failed"
    assert completed.error_code == "project_operation_in_progress"
    assert completed.progress == 100


@pytest.mark.asyncio
async def test_queued_worker_rejects_changed_compile_inputs(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'stale-worker.db'}")
    async with engine.begin() as connection:
        from app.db import Base

        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", maker)
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="sqlite+aiosqlite:///stale-worker.db",
            worker_lease_seconds=60,
        ),
    )
    async with maker() as session:
        from app.services.seed import seed_demo

        project = await seed_demo(session)
        job, _ = await create_operation(
            session,
            identity=AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {}),
            project=project,
            kind="compile",
            payload={"project_id": project.id},
            idempotency_key="stale-compile",
        )
        document = await session.scalar(
            select(Document).where(Document.project_id == project.id).limit(1)
        )
        assert document
        document.original_sha256 = "f" * 64
        await session.commit()
        job_id = job.id
    claimed = await worker.claim_one()
    assert claimed and claimed.id == job_id
    await worker.process_job(job_id)
    async with maker() as session:
        failed = await session.get(Job, job_id)
        assert failed and failed.status == "failed"
        assert failed.error_code == "stale_input"
    await engine.dispose()
