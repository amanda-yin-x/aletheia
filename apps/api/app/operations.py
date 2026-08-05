from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthIdentity
from app.config import get_settings
from app.models import (
    Build,
    Document,
    Finding,
    Job,
    PlacementDecision,
    Project,
    Rule,
    TestCase,
    UserAccount,
)
from app.schemas import OperationError, OperationOut
from app.services.canonical import content_hash
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.runner import run_comparison
from app.tenancy import ensure_account

RESOURCE_TYPES = {
    "compile": "build",
    "run": "run",
    "analyze": "project",
    "test_generation": "project",
}


async def operation_input_fingerprint(
    session: AsyncSession, *, kind: str, project_id: str, payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Capture the exact mutable inputs a queued operation is authorized to consume."""
    captured_payload = dict(payload)
    if kind == "compile":
        project = await session.get(Project, project_id)
        if project is None:
            raise ServiceError("project_not_found", "Project not found.", status_code=404)
        documents = list(
            (
                await session.scalars(
                    select(Document)
                    .where(Document.project_id == project_id)
                    .order_by(Document.id)
                )
            ).all()
        )
        rules = list(
            (
                await session.scalars(
                    select(Rule)
                    .where(Rule.project_id == project_id, Rule.status != "superseded")
                    .order_by(Rule.stable_key, Rule.revision)
                )
            ).all()
        )
        findings = list(
            (
                await session.scalars(
                    select(Finding)
                    .where(Finding.project_id == project_id)
                    .order_by(Finding.id)
                )
            ).all()
        )
        tests = list(
            (
                await session.scalars(
                    select(TestCase)
                    .where(TestCase.project_id == project_id)
                    .order_by(TestCase.stable_key)
                )
            ).all()
        )
        placements = list(
            (
                await session.scalars(
                    select(PlacementDecision)
                    .where(PlacementDecision.project_id == project_id)
                    .order_by(PlacementDecision.rule_id, PlacementDecision.version)
                )
            ).all()
        )
        snapshot: dict[str, Any] = {
            "project_configuration": [
                project.domain,
                project.compiler_profile,
                project.compilation_config,
            ],
            "documents": [
                [
                    item.id,
                    item.name,
                    item.original_sha256,
                    item.normalized_sha256,
                    item.version,
                    item.kind,
                    item.mime_type,
                    item.line_count,
                    item.origin,
                    item.authority_owner,
                    item.authority_status,
                    item.effective_at,
                    item.supersedes_document_id,
                    item.jurisdictions,
                    item.authority_scopes,
                    item.version_label,
                ]
                for item in documents
            ],
            "rules": [
                [
                    item.stable_key,
                    item.revision,
                    item.title,
                    item.status,
                    item.normative_text,
                    item.category,
                    item.effect,
                    item.severity,
                    item.confidence,
                    item.scope,
                    item.condition,
                    item.requires,
                    item.enforcement,
                    item.decidability,
                    item.source_refs,
                    item.target_tools,
                    item.exceptions,
                    item.reviewer_note,
                    item.provenance_kind,
                    item.provenance_metadata,
                ]
                for item in rules
            ],
            "findings": [
                [
                    item.id,
                    item.type,
                    item.severity,
                    item.related_rule_ids,
                    item.proof_status,
                    item.message,
                    item.witness,
                    item.resolution_state,
                    item.resolution_note,
                ]
                for item in findings
            ],
            "tests": [
                [
                    item.stable_key,
                    item.title,
                    item.provenance,
                    item.review_status,
                    item.spec,
                ]
                for item in tests
            ],
            "placements": [
                [
                    item.id,
                    item.rule_id,
                    item.version,
                    item.profile_name,
                    item.profile_version,
                    item.destinations,
                    item.scope_slug,
                    item.rendering,
                    item.transform_kind,
                    item.disposition,
                    item.rationale,
                    item.review_status,
                    item.reviewer,
                ]
                for item in placements
            ],
        }
    elif kind == "run":
        build_id = captured_payload.get("build_id")
        build = (
            await session.get(Build, str(build_id))
            if build_id
            else await session.scalar(
                select(Build)
                .where(Build.project_id == project_id)
                .order_by(Build.created_at.desc())
            )
        )
        if build is None:
            raise ServiceError(
                "build_required",
                "Build a candidate before running the comparison.",
                status_code=409,
            )
        if build.project_id != project_id:
            raise ServiceError("build_not_found", "Build not found.", status_code=404)
        captured_payload["build_id"] = build.id
        snapshot = {
            "build": [build.id, build.content_hash],
            "adapter": captured_payload.get("adapter", "fixture"),
        }
    else:
        snapshot = {"project_id": project_id}
    return content_hash(snapshot), captured_payload


async def validate_operation_input(session: AsyncSession, job: Job) -> None:
    if job.kind not in {"compile", "run"}:
        return
    requested = job.payload.get("input_fingerprint")
    current, _ = await operation_input_fingerprint(
        session,
        kind=job.kind,
        project_id=job.project_id,
        payload=job.payload,
    )
    if not isinstance(requested, str) or requested != current:
        raise ServiceError(
            "stale_input",
            "Project inputs changed after this operation was requested. Submit it again.",
            status_code=409,
        )


async def lock_operation_project(session: AsyncSession, job: Job) -> Project:
    """Serialize a snapshot-consuming operation with project mutations."""

    project = await session.scalar(
        select(Project)
        .where(
            Project.id == job.project_id,
            Project.workspace_id == job.workspace_id,
        )
        .with_for_update()
    )
    if project is None or job.payload.get("project_id") != project.id:
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    return project


def operation_out(job: Job) -> OperationOut:
    error = None
    if job.error_code:
        error = OperationError(
            code=job.error_code,
            message=job.error_message or "The operation could not be completed.",
        )
    return OperationOut.model_validate(
        {
            "id": job.id,
            "workspace_id": job.workspace_id,
            "kind": job.kind,
            "status": job.status,
            "progress": job.progress,
            "resource_type": RESOURCE_TYPES.get(job.kind),
            "resource_id": job.resource_id,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "error": error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
    )


async def expire_stale_inline_operation(session: AsyncSession, job: Job) -> Job:
    lease = job.lease_expiry
    if lease is not None and lease.tzinfo is None:
        lease = lease.replace(tzinfo=UTC)
    if (
        job.status == "running"
        and (job.owner or "").startswith("inline-")
        and lease is not None
        and lease <= datetime.now(UTC)
    ):
        job.status = "failed"
        job.progress = 100
        job.owner = None
        job.lease_expiry = None
        job.error_code = "operation_interrupted"
        job.error_message = "The inline operation was interrupted. Submit it again."
        job.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(job)
    return job


async def _owned_inline_job(session: AsyncSession, job_id: str, owner: str) -> Job | None:
    job: Job | None = await session.scalar(
        select(Job)
        .where(Job.id == job_id, Job.status == "running", Job.owner == owner)
        .execution_options(populate_existing=True)
    )
    return job


async def create_operation(
    session: AsyncSession,
    *,
    identity: AuthIdentity,
    project: Project,
    kind: str,
    payload: dict[str, Any],
    idempotency_key: str | None,
) -> tuple[Job, bool]:
    key = (idempotency_key or str(uuid4())).strip()
    if not key or len(key) > 255:
        raise ServiceError(
            "invalid_idempotency_key",
            "Idempotency-Key must contain between 1 and 255 characters.",
        )
    fingerprint = content_hash(
        {"workspace_id": project.workspace_id, "project_id": project.id, "kind": kind, "payload": payload}
    )
    existing = await session.scalar(
        select(Job).where(
            Job.workspace_id == project.workspace_id,
            Job.project_id == project.id,
            Job.kind == kind,
            Job.idempotency_key == key,
        )
    )
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ServiceError(
                "idempotency_conflict",
                "This Idempotency-Key was already used for a different request.",
                status_code=409,
            )
        return existing, False
    input_fingerprint, captured_payload = await operation_input_fingerprint(
        session, kind=kind, project_id=project.id, payload=payload
    )
    captured_payload["input_fingerprint"] = input_fingerprint
    account = await ensure_account(session, identity)
    if identity.is_anonymous:
        # The counter belongs to the account, not the project, so resetting a
        # fixture cannot reset the free guest allowance. Locking serializes
        # concurrent requests from the same guest across tabs.
        await session.flush()
        locked_account = await session.scalar(
            select(UserAccount)
            .where(UserAccount.id == account.id)
            .with_for_update()
        )
        if locked_account is None:
            raise ServiceError("authentication_required", "A valid user session is required.", status_code=401)
        if locked_account.guest_operation_count >= get_settings().guest_max_operations:
            raise ServiceError(
                "guest_operation_limit_reached",
                "This guest workspace has used its live-operation allowance. Sign in for a persistent workspace or start a new guest session.",
                status_code=429,
            )
        locked_account.guest_operation_count += 1
    job = Job(
        workspace_id=project.workspace_id,
        project_id=project.id,
        requested_by_user_id=identity.subject,
        kind=kind,
        payload=captured_payload,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        status="queued",
        progress=0,
        attempt_count=0,
        max_attempts=get_settings().worker_max_attempts,
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(Job).where(
                Job.workspace_id == project.workspace_id,
                Job.project_id == project.id,
                Job.kind == kind,
                Job.idempotency_key == key,
            )
        )
        if existing and existing.request_fingerprint == fingerprint:
            return existing, False
        raise ServiceError(
            "idempotency_conflict",
            "This Idempotency-Key was already used for a different request.",
            status_code=409,
        ) from None
    await session.refresh(job)
    return job, True


async def execute_inline(session: AsyncSession, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.status in {"succeeded", "failed", "dead_lettered", "cancelled"}:
        if job is None:
            raise ServiceError("job_not_found", "Job not found.", status_code=404)
        return job
    owner = f"inline-{uuid4()}"
    job.status = "running"
    job.progress = 10
    job.owner = owner
    job.lease_expiry = datetime.now(UTC) + timedelta(
        # Inline fixture work has no background heartbeat. Keep crash recovery,
        # but never let a normal cold-start request be declared stale mid-flight.
        seconds=max(get_settings().worker_lease_seconds, 15 * 60)
    )
    job.attempt_count += 1
    job.updated_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        queued = await session.get(Job, job_id)
        if queued is None:
            raise ServiceError("job_not_found", "Job not found.", status_code=404) from None
        queued.status = "failed"
        queued.progress = 100
        queued.owner = None
        queued.lease_expiry = None
        queued.error_code = "project_operation_in_progress"
        queued.error_message = "Another operation is already running for this project."
        queued.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(queued)
        return queued
    try:
        await lock_operation_project(session, job)
        await validate_operation_input(session, job)
        if job.kind == "compile":
            build = await compile_project(session, job.project_id)
            resource_id = build.id
        elif job.kind == "run":
            run = await run_comparison(
                session,
                job.project_id,
                str(job.payload["build_id"]) if job.payload.get("build_id") else None,
                run_id=job.id,
            )
            resource_id = run.id
        elif job.kind in {"analyze", "test_generation"}:
            resource_id = job.project_id
        else:
            raise ServiceError("unsupported_operation", "This operation type is not supported.")
    except ServiceError as error:
        await session.rollback()
        current = await _owned_inline_job(session, job_id, owner)
        if current:
            current.status = "failed"
            current.progress = 100
            current.owner = None
            current.lease_expiry = None
            current.error_code = error.code
            current.error_message = error.message
            current.updated_at = datetime.now(UTC)
            await session.commit()
            return current
        interrupted = await session.get(Job, job_id)
        if interrupted:
            return interrupted
        raise
    except Exception:
        await session.rollback()
        current = await _owned_inline_job(session, job_id, owner)
        if current:
            current.status = "failed"
            current.progress = 100
            current.owner = None
            current.lease_expiry = None
            current.error_code = "operation_failed"
            current.error_message = "The operation could not be completed."
            current.updated_at = datetime.now(UTC)
            await session.commit()
            return current
        interrupted = await session.get(Job, job_id)
        if interrupted:
            return interrupted
        raise
    current = await _owned_inline_job(session, job_id, owner)
    if current is None:
        interrupted = await session.get(Job, job_id)
        if interrupted:
            return interrupted
        raise ServiceError("job_not_found", "Job not found.", status_code=404)
    current.status = "succeeded"
    current.progress = 100
    current.resource_id = resource_id
    current.owner = None
    current.lease_expiry = None
    current.error_code = None
    current.error_message = None
    current.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(current)
    return current
