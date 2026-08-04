from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    TraceEventModel,
    UserAccount,
    WaitlistSignup,
    Workspace,
    WorkspaceMembership,
)


@dataclass(frozen=True, slots=True)
class GuestCleanupResult:
    cutoff: str
    guest_accounts: int
    auth_only_accounts: int
    workspaces: int
    projects: int
    linked_waitlist_signups: int
    executed: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def cleanup_expired_guests(
    session: AsyncSession,
    *,
    older_than_days: int,
    execute: bool,
    now: datetime | None = None,
) -> GuestCleanupResult:
    """Count or atomically remove expired guest identities and workspace data."""
    if older_than_days < 1:
        raise ValueError("older_than_days must be at least 1")
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(days=older_than_days)
    candidate_ids = list(
        (
            await session.scalars(
                select(UserAccount.id).where(
                    UserAccount.is_anonymous.is_(True),
                    UserAccount.created_at < cutoff,
                )
            )
        ).all()
    )
    postgres = session.bind is not None and session.bind.dialect.name == "postgresql"
    if candidate_ids and postgres:
        # Supabase Auth is authoritative for guest-to-permanent conversion.
        # During execution, lock every matching Auth row before deciding which
        # public rows are still anonymous. This makes conversion and cleanup
        # mutually exclusive: a committed conversion is preserved, while a
        # conversion that starts after cleanup waits for the guest deletion.
        # Dry runs deliberately retain a plain, non-locking read.
        lock_clause = " FOR UPDATE" if execute else ""
        auth_rows = (
            await session.execute(
                text(
                    "SELECT id::text, is_anonymous FROM auth.users "
                    "WHERE id::text = ANY(CAST(:guest_ids AS text[])) "
                    "ORDER BY id"
                    f"{lock_clause}"
                ),
                {"guest_ids": candidate_ids},
            )
        ).all()
        auth_states = {
            str(auth_id): bool(is_anonymous) for auth_id, is_anonymous in auth_rows
        }
        candidate_ids = [
            guest_id
            for guest_id in candidate_ids
            # An application-only orphan remains cleanup-eligible. Existing
            # Auth rows are eligible only while the locked row is anonymous.
            if auth_states.get(guest_id, True)
        ]

    auth_only_ids: list[str] = []
    if postgres:
        lock_clause = " FOR UPDATE OF users" if execute else ""
        auth_only_ids = list(
            (
                await session.scalars(
                    text(
                        "SELECT users.id::text FROM auth.users AS users "
                        "WHERE users.is_anonymous IS TRUE "
                        "AND users.created_at < :cutoff "
                        "AND NOT EXISTS ("
                        "SELECT 1 FROM public.user_accounts AS accounts "
                        "WHERE accounts.id = users.id::text"
                        ") ORDER BY users.id"
                        f"{lock_clause}"
                    ),
                    {"cutoff": cutoff},
                )
            ).all()
        )

    if candidate_ids:
        workspace_ids = list(
            (
                await session.scalars(
                    select(Workspace.id).where(
                        Workspace.created_by_user_id.in_(candidate_ids)
                    )
                )
            ).all()
        )
        workspace_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.created_by_user_id.in_(candidate_ids))
            )
            or 0
        )
        project_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Project)
                .join(Workspace, Project.workspace_id == Workspace.id)
                .where(Workspace.created_by_user_id.in_(candidate_ids))
            )
            or 0
        )
        waitlist_count = int(
            await session.scalar(
                select(func.count())
                .select_from(WaitlistSignup)
                .where(WaitlistSignup.user_id.in_(candidate_ids))
            )
            or 0
        )
    else:
        workspace_ids = []
        workspace_count = project_count = waitlist_count = 0

    result = GuestCleanupResult(
        cutoff=cutoff.isoformat(),
        guest_accounts=len(candidate_ids),
        auth_only_accounts=len(auth_only_ids),
        workspaces=workspace_count,
        projects=project_count,
        linked_waitlist_signups=waitlist_count,
        executed=execute,
    )
    if not execute or (not candidate_ids and not auth_only_ids):
        return result

    # Delete in explicit dependency order as well as retaining database
    # cascades. This keeps cleanup correct in SQLite tests and resilient if a
    # historical hosted constraint predates the current ON DELETE settings.
    if workspace_ids:
        project_ids = select(Project.id).where(Project.workspace_id.in_(workspace_ids))
        run_ids = select(Run.id).where(Run.project_id.in_(project_ids))
        result_ids = select(ScenarioResult.id).where(ScenarioResult.run_id.in_(run_ids))
        await session.execute(
            delete(TraceEventModel).where(TraceEventModel.result_id.in_(result_ids))
        )
        await session.execute(delete(Report).where(Report.run_id.in_(run_ids)))
        await session.execute(
            delete(ScenarioResult).where(ScenarioResult.run_id.in_(run_ids))
        )
        await session.execute(delete(Run).where(Run.project_id.in_(project_ids)))
        await session.execute(delete(Build).where(Build.project_id.in_(project_ids)))
        await session.execute(delete(TestCase).where(TestCase.project_id.in_(project_ids)))
        await session.execute(delete(Finding).where(Finding.project_id.in_(project_ids)))
        await session.execute(delete(Rule).where(Rule.project_id.in_(project_ids)))
        await session.execute(delete(Document).where(Document.project_id.in_(project_ids)))
        await session.execute(delete(Job).where(Job.project_id.in_(project_ids)))
        await session.execute(delete(Project).where(Project.workspace_id.in_(workspace_ids)))
    if candidate_ids:
        await session.execute(
            delete(Workspace).where(Workspace.created_by_user_id.in_(candidate_ids))
        )
        await session.execute(
            delete(WorkspaceMembership).where(
                WorkspaceMembership.user_id.in_(candidate_ids)
            )
        )
        await session.execute(
            update(WaitlistSignup)
            .where(WaitlistSignup.user_id.in_(candidate_ids))
            .values(user_id=None)
        )
        await session.execute(
            delete(UserAccount).where(UserAccount.id.in_(candidate_ids))
        )
    auth_delete_ids = list(dict.fromkeys([*candidate_ids, *auth_only_ids]))
    if postgres and auth_delete_ids:
        await session.execute(
            text(
                "DELETE FROM auth.users "
                "WHERE is_anonymous IS TRUE "
                "AND id::text = ANY(CAST(:guest_ids AS text[]))"
            ),
            {"guest_ids": auth_delete_ids},
        )
    await session.commit()
    return result
