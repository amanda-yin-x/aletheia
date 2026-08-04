from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import LOCAL_USER_EMAIL, LOCAL_USER_ID, AuthIdentity
from app.config import get_settings
from app.models import (
    Build,
    Document,
    Finding,
    Job,
    Project,
    Report,
    Rule,
    Run,
    ScenarioResult,
    TestCase,
    UserAccount,
    Workspace,
    WorkspaceMembership,
)
from app.services.errors import ServiceError

LOCAL_WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"
READ_ROLES = frozenset({"owner", "admin", "editor", "viewer"})
WRITE_ROLES = frozenset({"owner", "admin", "editor"})
ADMIN_ROLES = frozenset({"owner", "admin"})


def _not_found(resource: str) -> ServiceError:
    return ServiceError(f"{resource}_not_found", f"{resource.replace('_', ' ').title()} not found.", status_code=404)


async def ensure_account(session: AsyncSession, identity: AuthIdentity) -> UserAccount:
    account = await session.get(UserAccount, identity.subject)
    if account is None:
        created_at: datetime | None = None
        if (
            identity.is_anonymous
            and session.bind is not None
            and session.bind.dialect.name == "postgresql"
        ):
            created_at = await session.scalar(
                text(
                    "SELECT created_at FROM auth.users "
                    "WHERE id::text = :subject AND is_anonymous IS TRUE"
                ),
                {"subject": identity.subject},
            )
            if created_at is None:
                raise ServiceError(
                    "authentication_required",
                    "A valid user session is required.",
                    status_code=401,
                )
        account = UserAccount(
            id=identity.subject,
            email=identity.email,
            is_anonymous=identity.is_anonymous,
            **({"created_at": created_at} if created_at is not None else {}),
        )
        session.add(account)
        try:
            await session.flush()
        except IntegrityError:
            # Concurrent first-login requests may race on the JWT subject. The
            # winning transaction owns creation; recover its committed account.
            await session.rollback()
            account = await session.get(UserAccount, identity.subject)
            if account is None:
                raise
    elif identity.email and identity.email != account.email:
        account.email = identity.email
    if account.is_anonymous != identity.is_anonymous:
        account.is_anonymous = identity.is_anonymous
    return account


async def enforce_guest_session(session: AsyncSession, identity: AuthIdentity) -> None:
    """Create a durable guest ledger and expire browser-scoped demos after a fixed TTL."""
    if not identity.is_anonymous:
        return
    account = await session.get(UserAccount, identity.subject)
    created = account is None
    if account is None:
        account = await ensure_account(session, identity)
    created_at = account.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    expires_at = created_at + timedelta(hours=get_settings().guest_session_ttl_hours)
    if expires_at <= datetime.now(UTC):
        # A first request can arrive from an old Supabase anonymous identity
        # that never bootstrapped an application account. Do not commit the
        # newly flushed ledger before applying the same TTL as every later
        # request; rollback prevents an expired first access leaving residue.
        if created:
            await session.rollback()
        raise ServiceError(
            "guest_session_expired",
            "This guest demo has expired. Sign out and open a new guest workspace.",
            status_code=401,
        )
    if created:
        await session.commit()


async def consume_guest_mutation(session: AsyncSession, identity: AuthIdentity) -> None:
    """Bound every successful guest write independently of resettable project rows."""
    if not identity.is_anonymous:
        return
    account = await ensure_account(session, identity)
    await session.flush()
    locked_account = await session.scalar(
        select(UserAccount).where(UserAccount.id == account.id).with_for_update()
    )
    if locked_account is None:
        raise ServiceError(
            "authentication_required",
            "A valid user session is required.",
            status_code=401,
        )
    if locked_account.guest_mutation_count >= get_settings().guest_max_mutations:
        raise ServiceError(
            "guest_mutation_limit_reached",
            "This guest workspace has reached its change allowance. Sign in for a persistent workspace or start a new guest session.",
            status_code=429,
        )
    locked_account.guest_mutation_count += 1


async def ensure_local_workspace(session: AsyncSession) -> Workspace:
    identity = AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {"local": True})
    await ensure_account(session, identity)
    workspace = await session.get(Workspace, LOCAL_WORKSPACE_ID)
    if workspace is None:
        workspace = Workspace(
            id=LOCAL_WORKSPACE_ID,
            slug="local-workspace",
            name="Local workspace",
            created_by_user_id=LOCAL_USER_ID,
        )
        session.add(workspace)
        await session.flush()
    membership = await session.get(
        WorkspaceMembership,
        {"workspace_id": LOCAL_WORKSPACE_ID, "user_id": LOCAL_USER_ID},
    )
    if membership is None:
        session.add(
            WorkspaceMembership(
                workspace_id=LOCAL_WORKSPACE_ID, user_id=LOCAL_USER_ID, role="owner"
            )
        )
        await session.flush()
    return workspace


async def require_workspace(
    session: AsyncSession,
    identity: AuthIdentity,
    workspace_id: str,
    *,
    write: bool = False,
    admin: bool = False,
) -> tuple[Workspace, WorkspaceMembership]:
    allowed = ADMIN_ROLES if admin else WRITE_ROLES if write else READ_ROLES
    row = (
        await session.execute(
            select(Workspace, WorkspaceMembership)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.workspace_id == Workspace.id,
            )
            .where(
                Workspace.id == workspace_id,
                WorkspaceMembership.user_id == identity.subject,
                WorkspaceMembership.role.in_(allowed),
            )
        )
    ).one_or_none()
    if row is None:
        raise _not_found("workspace")
    return row[0], row[1]


async def scoped_project(
    session: AsyncSession, identity: AuthIdentity, project_id: str, *, write: bool = False
) -> Project:
    allowed = WRITE_ROLES if write else READ_ROLES
    statement = (
        select(Project)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Project.workspace_id)
        .where(
            Project.id == project_id,
            WorkspaceMembership.user_id == identity.subject,
            WorkspaceMembership.role.in_(allowed),
        )
    )
    if write:
        statement = statement.with_for_update()
    project = await session.scalar(statement)
    if project is None:
        raise _not_found("project")
    return project


async def _scoped_project_resource[Resource](
    session: AsyncSession,
    identity: AuthIdentity,
    model: type[Resource],
    resource_id: str,
    *,
    write: bool,
    resource_name: str,
) -> Resource:
    allowed = WRITE_ROLES if write else READ_ROLES
    if write:
        # Every project-data mutation takes locks in the same order as build
        # and run execution: Project first, then the child row. This prevents
        # a revision from changing after an operation validates its snapshot.
        project_id = await session.scalar(
            select(model.project_id)  # type: ignore[attr-defined]
            .join(Project, model.project_id == Project.id)  # type: ignore[attr-defined]
            .join(
                WorkspaceMembership,
                WorkspaceMembership.workspace_id == Project.workspace_id,
            )
            .where(
                model.id == resource_id,  # type: ignore[attr-defined]
                WorkspaceMembership.user_id == identity.subject,
                WorkspaceMembership.role.in_(allowed),
            )
        )
        if project_id is None:
            raise _not_found(resource_name)
        await scoped_project(session, identity, str(project_id), write=True)
        resource = await session.scalar(
            select(model)
            .where(
                model.id == resource_id,  # type: ignore[attr-defined]
                model.project_id == project_id,  # type: ignore[attr-defined]
            )
            .with_for_update()
        )
        if resource is None:
            raise _not_found(resource_name)
        return resource

    statement = (
        select(model)
        .join(Project, model.project_id == Project.id)  # type: ignore[attr-defined]
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Project.workspace_id)
        .where(
            model.id == resource_id,  # type: ignore[attr-defined]
            WorkspaceMembership.user_id == identity.subject,
            WorkspaceMembership.role.in_(allowed),
        )
    )
    resource = await session.scalar(statement)
    if resource is None:
        raise _not_found(resource_name)
    return cast(Resource, resource)


async def scoped_document(session: AsyncSession, identity: AuthIdentity, value: str) -> Document:
    return await _scoped_project_resource(session, identity, Document, value, write=False, resource_name="document")


async def scoped_rule(session: AsyncSession, identity: AuthIdentity, value: str, *, write: bool = False) -> Rule:
    return await _scoped_project_resource(session, identity, Rule, value, write=write, resource_name="rule")


async def scoped_finding(session: AsyncSession, identity: AuthIdentity, value: str, *, write: bool = False) -> Finding:
    return await _scoped_project_resource(session, identity, Finding, value, write=write, resource_name="finding")


async def scoped_build(session: AsyncSession, identity: AuthIdentity, value: str) -> Build:
    return await _scoped_project_resource(session, identity, Build, value, write=False, resource_name="build")


async def scoped_test(session: AsyncSession, identity: AuthIdentity, value: str, *, write: bool = False) -> TestCase:
    return await _scoped_project_resource(session, identity, TestCase, value, write=write, resource_name="test")


async def scoped_run(session: AsyncSession, identity: AuthIdentity, value: str, *, write: bool = False) -> Run:
    return await _scoped_project_resource(session, identity, Run, value, write=write, resource_name="run")


async def scoped_result(session: AsyncSession, identity: AuthIdentity, value: str) -> ScenarioResult:
    result = await session.scalar(
        select(ScenarioResult)
        .join(Run, ScenarioResult.run_id == Run.id)
        .join(Project, Run.project_id == Project.id)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Project.workspace_id)
        .where(
            ScenarioResult.id == value,
            WorkspaceMembership.user_id == identity.subject,
            WorkspaceMembership.role.in_(READ_ROLES),
        )
    )
    if result is None:
        raise _not_found("result")
    return result


async def scoped_report(session: AsyncSession, identity: AuthIdentity, value: str) -> Report:
    report = await session.scalar(
        select(Report)
        .join(Run, Report.run_id == Run.id)
        .join(Project, Run.project_id == Project.id)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Project.workspace_id)
        .where(
            Report.id == value,
            WorkspaceMembership.user_id == identity.subject,
            WorkspaceMembership.role.in_(READ_ROLES),
        )
    )
    if report is None:
        raise _not_found("report")
    return report


async def scoped_job(session: AsyncSession, identity: AuthIdentity, value: str) -> Job:
    job = await session.scalar(
        select(Job)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Job.workspace_id)
        .where(
            Job.id == value,
            WorkspaceMembership.user_id == identity.subject,
            WorkspaceMembership.role.in_(READ_ROLES),
        )
    )
    if job is None:
        raise _not_found("job")
    return job
