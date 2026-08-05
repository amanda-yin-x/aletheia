from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import get_settings
from app.db import SessionLocal
from app.models import Job, Project
from app.operations import lock_operation_project, validate_operation_input
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.runner import run_comparison

logger = logging.getLogger(__name__)


async def recover_expired_leases(session: AsyncSession) -> tuple[int, int]:
    """Return expired work to the queue, or dead-letter exhausted operations."""
    now = datetime.now(UTC)
    jobs = list(
        (
            await session.scalars(
                select(Job).where(
                    Job.status == "running",
                    Job.lease_expiry.is_not(None),
                    Job.lease_expiry <= now,
                )
            )
        ).all()
    )
    recovered = dead_lettered = 0
    for job in jobs:
        job.owner = None
        job.lease_expiry = None
        job.updated_at = now
        if job.attempt_count >= job.max_attempts:
            job.status = "dead_lettered"
            job.progress = 100
            job.error_code = "retry_limit_exceeded"
            job.error_message = "The operation exceeded its retry limit."
            dead_lettered += 1
        else:
            job.status = "queued"
            job.progress = 0
            recovered += 1
    if jobs:
        await session.commit()
    return recovered, dead_lettered


async def claim_one(*, worker_id: str | None = None) -> Job | None:
    settings = get_settings()
    owner = worker_id or f"worker-{uuid4()}"
    async with SessionLocal() as session:
        await recover_expired_leases(session)
        running = aliased(Job)
        project_busy = exists(
            select(running.id).where(
                running.project_id == Job.project_id,
                running.status == "running",
            )
        )
        statement = (
            select(Job)
            .where(
                Job.status == "queued",
                Job.attempt_count < Job.max_attempts,
                ~project_busy,
            )
            .order_by(Job.created_at)
            .limit(1)
        )
        if not settings.database_url.startswith("sqlite"):
            statement = statement.with_for_update(skip_locked=True)
        job = await session.scalar(statement)
        if job is None:
            return None
        job.status = "running"
        job.progress = max(job.progress, 5)
        job.owner = owner
        job.attempt_count += 1
        job.lease_expiry = datetime.now(UTC) + timedelta(seconds=settings.worker_lease_seconds)
        job.updated_at = datetime.now(UTC)
        try:
            await session.commit()
        except IntegrityError:
            # The partial unique index arbitrates concurrent claims for one project.
            await session.rollback()
            return None
        await session.refresh(job)
        return job


async def _validated_job_project(session: AsyncSession, job: Job) -> Project:
    project = await session.scalar(
        select(Project).where(
            Project.id == job.project_id,
            Project.workspace_id == job.workspace_id,
        )
    )
    if project is None or job.payload.get("project_id") != project.id:
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    return project


async def _owned_job(session: AsyncSession, job_id: str, owner: str) -> Job | None:
    job: Job | None = await session.scalar(
        select(Job)
        .where(Job.id == job_id, Job.status == "running", Job.owner == owner)
        .execution_options(populate_existing=True)
    )
    return job


@asynccontextmanager
async def _lease_heartbeat(job_id: str, owner: str) -> AsyncIterator[None]:
    stop = asyncio.Event()

    async def heartbeat() -> None:
        settings = get_settings()
        interval = max(1.0, settings.worker_lease_seconds / 3)
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                async with SessionLocal() as heartbeat_session:
                    current = await _owned_job(heartbeat_session, job_id, owner)
                    if current is None:
                        return
                    current.lease_expiry = datetime.now(UTC) + timedelta(
                        seconds=settings.worker_lease_seconds
                    )
                    current.updated_at = datetime.now(UTC)
                    await heartbeat_session.commit()

    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        stop.set()
        await task


async def _process_owned_job(session: AsyncSession, job: Job, lease_owner: str) -> None:
    job_id = job.id
    try:
        project = await _validated_job_project(session, job)
        job.progress = 20
        job.updated_at = datetime.now(UTC)
        await session.commit()
        project = await lock_operation_project(session, job)
        await validate_operation_input(session, job)
        if job.kind == "compile":
            build = await compile_project(session, project.id)
            resource_id = build.id
        elif job.kind == "run":
            run = await run_comparison(
                session,
                project.id,
                str(job.payload["build_id"]) if job.payload.get("build_id") else None,
                run_id=job.id,
            )
            resource_id = run.id
        elif job.kind in {"analyze", "test_generation"}:
            resource_id = project.id
        else:
            raise ServiceError("unsupported_operation", "This operation type is not supported.")
    except ServiceError as error:
        await session.rollback()
        current = await _owned_job(session, job_id, lease_owner)
        if current:
            current.status = "failed"
            current.progress = 100
            current.owner = None
            current.lease_expiry = None
            current.error_code = error.code
            current.error_message = error.message
            current.updated_at = datetime.now(UTC)
            await session.commit()
        return
    except Exception:
        logger.exception("Operation execution failed", extra={"job_id": job_id})
        await session.rollback()
        current = await _owned_job(session, job_id, lease_owner)
        if current:
            exhausted = current.attempt_count >= current.max_attempts
            current.status = "dead_lettered" if exhausted else "queued"
            current.progress = 100 if exhausted else 0
            current.owner = None
            current.lease_expiry = None
            current.error_code = (
                "retry_limit_exceeded" if exhausted else "operation_retry_scheduled"
            )
            current.error_message = (
                "The operation exceeded its retry limit."
                if exhausted
                else "The operation will be retried."
            )
            current.updated_at = datetime.now(UTC)
            await session.commit()
        return
    current = await _owned_job(session, job_id, lease_owner)
    if current:
        current.status = "succeeded"
        current.progress = 100
        current.resource_id = resource_id
        current.owner = None
        current.lease_expiry = None
        current.error_code = None
        current.error_message = None
        current.updated_at = datetime.now(UTC)
        await session.commit()


async def process_job(job_id: str, *, expected_owner: str | None = None) -> None:
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != "running":
            return
        lease_owner = expected_owner or job.owner
        if lease_owner is None or job.owner != lease_owner:
            return
        async with _lease_heartbeat(job_id, lease_owner):
            await _process_owned_job(session, job, lease_owner)


async def run_worker(*, once: bool = False) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    registered: list[signal.Signals] = []
    for name in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(name, stop.set)
            registered.append(name)
        except NotImplementedError:  # pragma: no cover - Windows event loops
            pass
    worker_id = f"worker-{uuid4()}"
    try:
        while not stop.is_set():
            job = await claim_one(worker_id=worker_id)
            if job:
                await process_job(job.id, expected_owner=worker_id)
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=get_settings().worker_poll_seconds)
            except TimeoutError:
                pass
    finally:
        for name in registered:
            loop.remove_signal_handler(name)
