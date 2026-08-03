from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, create_schema
from app.models import Job
from app.services.compiler import compile_project
from app.services.runner import run_comparison


async def claim_one() -> Job | None:
    async with SessionLocal() as session:
        statement = select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1)
        if not get_settings().database_url.startswith("sqlite"):
            statement = statement.with_for_update(skip_locked=True)
        job = await session.scalar(statement)
        if not job:
            return None
        job.status = "running"
        job.owner = f"worker-{uuid4()}"
        job.attempt_count += 1
        job.lease_expiry = datetime.now(UTC) + timedelta(seconds=get_settings().worker_lease_seconds)
        job.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(job)
        return job


async def process_job(job_id: str) -> None:
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return
        try:
            if job.kind == "compile":
                build_resource = await compile_project(session, str(job.payload["project_id"]))
                resource_id = build_resource.id
            elif job.kind == "run":
                run_resource = await run_comparison(
                    session,
                    str(job.payload["project_id"]),
                    str(job.payload["build_id"]) if job.payload.get("build_id") else None,
                )
                resource_id = run_resource.id
            elif job.kind in {"analyze", "test_generation"}:
                resource_id = str(job.payload["project_id"])
            else:
                raise ValueError(f"No worker handler is registered for {job.kind}")
            current = await session.get(Job, job_id)
            if current:
                current.status = "succeeded"
                current.progress = 100
                current.resource_id = resource_id
                current.updated_at = datetime.now(UTC)
                await session.commit()
        except Exception as error:
            current = await session.get(Job, job_id)
            if current:
                current.status = "failed"
                current.error_code = "job_execution_failed"
                current.error_message = str(error)[:1000]
                current.updated_at = datetime.now(UTC)
                await session.commit()


async def run_worker(*, once: bool = False) -> None:
    await create_schema()
    while True:
        job = await claim_one()
        if job:
            await process_job(job.id)
        if once:
            return
        await asyncio.sleep(get_settings().worker_poll_seconds)
