from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthIdentity, require_identity, require_origin_token
from app.config import get_settings
from app.db import get_session
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
    Workspace,
    WorkspaceMembership,
)
from app.operations import (
    create_operation,
    execute_inline,
    expire_stale_inline_operation,
    operation_out,
)
from app.schemas import (
    BuildOut,
    DocumentOut,
    FindingOut,
    FindingPatch,
    MeOut,
    OperationOut,
    ProjectCreate,
    ProjectOut,
    ReportOut,
    RuleOut,
    RulePatch,
    RuleReview,
    RunCreate,
    RunOut,
    ScenarioResultOut,
    TestCaseOut,
    TestCasePatch,
    WorkspaceBootstrap,
    WorkspaceBootstrapOut,
    WorkspaceOut,
)
from app.services.canonical import (
    artifact_bytes,
    bytes_hash,
    canonical_json_bytes,
    content_hash,
    token_estimate,
)
from app.services.errors import ServiceError
from app.services.ingestion import NORMALIZER_VERSION, PARSER_VERSION, parse_document
from app.services.reporting import create_report
from app.services.review import resolve_finding, revise_rule
from app.services.seed import seed_demo
from app.tenancy import (
    ensure_account,
    require_workspace,
    scoped_build,
    scoped_document,
    scoped_finding,
    scoped_job,
    scoped_project,
    scoped_report,
    scoped_result,
    scoped_rule,
    scoped_run,
    scoped_test,
)

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_origin_token), Depends(require_identity)],
)


def _workspace_out(workspace: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id,
        slug=workspace.slug,
        name=workspace.name,
        role=role,
        created_at=workspace.created_at,
    )


async def _submit_operation(
    session: AsyncSession,
    response: Response,
    identity: AuthIdentity,
    project: Project,
    *,
    kind: str,
    payload: dict[str, Any],
    idempotency_key: str | None,
) -> OperationOut:
    settings = get_settings()
    normalized_idempotency_key = idempotency_key.strip() if idempotency_key is not None else None
    if settings.demo_inline_jobs:
        active = await session.scalar(
            select(Job).where(Job.project_id == project.id, Job.status == "running")
        )
        if active:
            active = await expire_stale_inline_operation(session, active)
            if active.status != "running":
                active = None
        if active:
            if (
                normalized_idempotency_key
                and active.kind == kind
                and active.idempotency_key == normalized_idempotency_key
            ):
                response.headers["Location"] = f"/api/v1/jobs/{active.id}"
                return operation_out(active)
            raise ServiceError(
                "project_operation_in_progress",
                "Another operation is already running for this project.",
                status_code=409,
            )
    job, _ = await create_operation(
        session,
        identity=identity,
        project=project,
        kind=kind,
        payload=payload,
        idempotency_key=normalized_idempotency_key,
    )
    if settings.demo_inline_jobs and job.status == "queued":
        job = await execute_inline(session, job.id)
    response.headers["Location"] = f"/api/v1/jobs/{job.id}"
    return operation_out(job)


@router.get("/config/public")
async def public_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "product": "Aletheia",
        "brand_line": "Policy CI for AI agents.",
        "demo_mode": settings.demo_mode,
        "uploads_enabled": not settings.demo_mode,
        "max_upload_bytes": settings.upload_max_bytes,
        "synthetic_data": True,
    }


@router.get("/me", response_model=MeOut)
async def get_me(
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    rows = (
        await session.execute(
            select(Workspace, WorkspaceMembership)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == identity.subject)
            .order_by(Workspace.created_at)
        )
    ).all()
    return MeOut(
        id=identity.subject,
        email=identity.email,
        workspaces=[_workspace_out(workspace, membership.role) for workspace, membership in rows],
    )


@router.post("/workspaces/bootstrap", response_model=WorkspaceBootstrapOut)
async def bootstrap_workspace(
    payload: WorkspaceBootstrap,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceBootstrapOut:
    await ensure_account(session, identity)
    existing = (
        await session.execute(
            select(Workspace, WorkspaceMembership)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(
                Workspace.created_by_user_id == identity.subject,
                WorkspaceMembership.user_id == identity.subject,
                WorkspaceMembership.role == "owner",
            )
            .order_by(Workspace.created_at)
            .limit(1)
        )
    ).one_or_none()
    created = existing is None
    if existing:
        workspace, membership = existing
    else:
        slug = payload.slug or f"personal-{content_hash(identity.subject)[:12]}"
        workspace = Workspace(
            slug=slug,
            name=payload.name,
            created_by_user_id=identity.subject,
        )
        session.add(workspace)
        try:
            await session.flush()
        except IntegrityError as error:
            await session.rollback()
            recovered = (
                await session.execute(
                    select(Workspace, WorkspaceMembership)
                    .join(
                        WorkspaceMembership,
                        WorkspaceMembership.workspace_id == Workspace.id,
                    )
                    .where(
                        Workspace.slug == slug,
                        Workspace.created_by_user_id == identity.subject,
                        WorkspaceMembership.user_id == identity.subject,
                        WorkspaceMembership.role == "owner",
                    )
                    .limit(1)
                )
            ).one_or_none()
            if recovered:
                workspace, membership = recovered
                project = await seed_demo(session, workspace_id=workspace.id)
                return WorkspaceBootstrapOut(
                    workspace=_workspace_out(workspace, membership.role),
                    project=ProjectOut.model_validate(project),
                    created=False,
                )
            raise ServiceError(
                "workspace_slug_unavailable",
                "That workspace slug is unavailable.",
                status_code=409,
            ) from error
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=identity.subject,
            role="owner",
        )
        session.add(membership)
        await session.commit()
        await session.refresh(workspace)
    project = await seed_demo(session, workspace_id=workspace.id)
    return WorkspaceBootstrapOut(
        workspace=_workspace_out(workspace, membership.role),
        project=ProjectOut.model_validate(project),
        created=created,
    )


@router.post("/workspaces/{workspace_id}/reset", response_model=ProjectOut)
async def reset_personal_workspace(
    workspace_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Project:
    workspace, _ = await require_workspace(session, identity, workspace_id, admin=True)
    northstar = await session.scalar(
        select(Project).where(
            Project.workspace_id == workspace.id,
            Project.slug == "northstar-retail",
        )
    )
    if northstar is not None:
        # Use the same tenant-aware row lock as project reset and all other
        # project mutations, so reset cannot delete an in-flight operation.
        await scoped_project(session, identity, northstar.id, write=True)
    return await seed_demo(session, workspace_id=workspace_id, reset=True)


@router.post("/projects/{project_id}/reset", response_model=ProjectOut)
async def reset_project(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await scoped_project(session, identity, project_id, write=True)
    await require_workspace(session, identity, project.workspace_id, admin=True)
    if project.slug != "northstar-retail":
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    reset = await seed_demo(session, workspace_id=project.workspace_id, reset=True)
    if reset.id != project_id:
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    return reset


@router.post(
    "/demo/reset",
    response_model=ProjectOut,
    summary="Reset local workspace",
    operation_id="reset_workspace",
)
async def reset_demo_workspace(
    x_demo_reset_secret: str | None = Header(default=None),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Project:
    settings = get_settings()
    if settings.hosted_mode or not settings.demo_mode:
        raise ServiceError(
            "demo_reset_disabled",
            "The local demo reset is disabled in this environment.",
            status_code=403,
        )
    if settings.demo_reset_secret and x_demo_reset_secret != settings.demo_reset_secret:
        raise ServiceError(
            "demo_reset_forbidden",
            "A valid workspace reset secret is required.",
            status_code=403,
        )
    membership = await session.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == identity.subject)
    )
    if membership is None:
        project = await seed_demo(session)
        return await seed_demo(session, workspace_id=project.workspace_id, reset=True)
    await require_workspace(session, identity, membership.workspace_id, admin=True)
    return await seed_demo(session, workspace_id=membership.workspace_id, reset=True)


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[Project]:
    return list(
        (
            await session.scalars(
                select(Project)
                .join(
                    WorkspaceMembership,
                    WorkspaceMembership.workspace_id == Project.workspace_id,
                )
                .where(WorkspaceMembership.user_id == identity.subject)
                .order_by(Project.created_at)
            )
        ).all()
    )


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectCreate,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Project:
    if get_settings().hosted_mode:
        raise ServiceError(
            "project_creation_disabled",
            "Hosted workspaces use the personal Northstar project.",
            status_code=403,
        )
    await require_workspace(session, identity, payload.workspace_id, write=True)
    project = Project(**payload.model_dump(), mode="local")
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ServiceError(
            "project_slug_unavailable",
            "That project slug is already in use in this workspace.",
            status_code=409,
        ) from error
    await session.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Project:
    return await scoped_project(session, identity, project_id)


@router.get("/projects/{project_id}/summary")
async def project_summary(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await scoped_project(session, identity, project_id)

    async def count(model: Any, *conditions: Any) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.project_id == project_id, *conditions)
            )
            or 0
        )

    current_build = await session.scalar(
        select(Build).where(Build.project_id == project_id).order_by(Build.created_at.desc())
    )
    last_run = await session.scalar(
        select(Run).where(Run.project_id == project_id).order_by(Run.started_at.desc())
    )
    return {
        "sources": await count(Document),
        "approved_rules": await count(Rule, Rule.status == "approved"),
        "critical_findings": await count(
            Finding,
            Finding.severity == "critical",
            Finding.resolution_state == "open",
        ),
        "tests": await count(TestCase, TestCase.review_status == "approved"),
        "current_build": BuildOut.model_validate(current_build).model_dump(mode="json")
        if current_build
        else None,
        "last_run": RunOut.model_validate(last_run).model_dump(mode="json") if last_run else None,
    }


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[Document]:
    await scoped_project(session, identity, project_id)
    return list(
        (
            await session.scalars(
                select(Document)
                .where(Document.project_id == project_id)
                .order_by(Document.created_at)
            )
        ).all()
    )


@router.post("/projects/{project_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    name: str | None = Form(default=None),
    kind: str = Form(default="policy"),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Document:
    await scoped_project(session, identity, project_id, write=True)
    settings = get_settings()
    if settings.demo_mode:
        raise ServiceError(
            "uploads_disabled_in_demo",
            "Uploads are disabled in this workspace.",
            status_code=403,
        )
    if file:
        raw = await file.read(settings.upload_max_bytes + 1)
        normalized, mime, provenance = parse_document(
            file.filename or "upload.txt", raw, max_bytes=settings.upload_max_bytes
        )
        document_name = file.filename or "upload.txt"
    elif text is not None:
        raw = text.encode()
        if len(raw) > settings.upload_max_bytes:
            raise ServiceError("file_too_large", "Pasted text exceeds the upload limit.")
        normalized = text.replace("\r\n", "\n")
        mime = "text/plain"
        provenance = {
            "locator": "normalized_line",
            "parser": "utf8_text",
            "parser_version": PARSER_VERSION,
            "normalizer": "aletheia_text",
            "normalizer_version": NORMALIZER_VERSION,
        }
        document_name = name or "pasted-source.txt"
    else:
        raise ServiceError("document_required", "Choose a file or paste text.")
    version = (
        int(
            await session.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.project_id == project_id, Document.name == document_name)
            )
            or 0
        )
        + 1
    )
    document = Document(
        project_id=project_id,
        kind=kind,
        name=document_name,
        version=version,
        original_sha256=bytes_hash(raw),
        normalized_sha256=bytes_hash(normalized.encode("utf-8")),
        normalized_text=normalized,
        mime_type=mime,
        line_count=len(normalized.splitlines()),
        token_estimate=token_estimate(normalized),
        origin={"type": "upload", **provenance},
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Document:
    return await scoped_document(session, identity, document_id)


@router.post("/projects/{project_id}/analysis-jobs", response_model=OperationOut, status_code=202)
async def analyze_project(
    project_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> OperationOut:
    project = await scoped_project(session, identity, project_id, write=True)
    return await _submit_operation(
        session,
        response,
        identity,
        project,
        kind="analyze",
        payload={"project_id": project_id, "extractor": "fixture"},
        idempotency_key=idempotency_key,
    )


@router.get("/projects/{project_id}/rules", response_model=list[RuleOut])
async def list_rules(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[Rule]:
    await scoped_project(session, identity, project_id)
    return list(
        (
            await session.scalars(
                select(Rule)
                .where(Rule.project_id == project_id, Rule.status != "superseded")
                .order_by(Rule.severity.desc(), Rule.title)
            )
        ).all()
    )


@router.get("/rules/{rule_id}", response_model=RuleOut)
async def get_rule(
    rule_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Rule:
    return await scoped_rule(session, identity, rule_id)


@router.patch("/rules/{rule_id}", response_model=RuleOut)
async def patch_rule(
    rule_id: str,
    payload: RulePatch,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Rule:
    await scoped_rule(session, identity, rule_id, write=True)
    return await revise_rule(
        session,
        rule_id,
        expected_revision=payload.expected_revision,
        changes=payload.model_dump(exclude={"expected_revision"}, exclude_none=True),
    )


async def _review_rule(
    session: AsyncSession,
    identity: AuthIdentity,
    rule_id: str,
    payload: RuleReview,
    status: str,
) -> Rule:
    await scoped_rule(session, identity, rule_id, write=True)
    expected = payload.expected_revision
    default_note = (
        "Approved after source and boundary review."
        if status == "approved"
        else "Rejected during policy review."
    )
    return await revise_rule(
        session,
        rule_id,
        expected_revision=expected,
        changes={"reviewer_note": payload.reviewer_note or default_note},
        status=status,
    )


@router.post("/rules/{rule_id}/approve", response_model=RuleOut)
async def approve_rule(
    rule_id: str,
    payload: RuleReview,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Rule:
    return await _review_rule(session, identity, rule_id, payload, "approved")


@router.post("/rules/{rule_id}/reject", response_model=RuleOut)
async def reject_rule(
    rule_id: str,
    payload: RuleReview,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Rule:
    return await _review_rule(session, identity, rule_id, payload, "rejected")


@router.get("/projects/{project_id}/findings", response_model=list[FindingOut])
async def list_findings(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[Finding]:
    await scoped_project(session, identity, project_id)
    return list(
        (
            await session.scalars(
                select(Finding)
                .where(Finding.project_id == project_id)
                .order_by(Finding.severity.desc(), Finding.created_at)
            )
        ).all()
    )


@router.patch("/findings/{finding_id}", response_model=FindingOut)
async def patch_finding(
    finding_id: str,
    payload: FindingPatch,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Finding:
    await scoped_finding(session, identity, finding_id, write=True)
    return await resolve_finding(
        session,
        finding_id,
        payload.resolution_state,
        payload.resolution_note,
        expected_state=payload.expected_resolution_state,
        winner_rule_id=payload.winner_rule_id,
        loser_rule_id=payload.loser_rule_id,
        authority=payload.authority,
        actor=identity.subject,
    )


@router.post("/projects/{project_id}/builds", response_model=OperationOut, status_code=202)
async def create_build(
    project_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> OperationOut:
    project = await scoped_project(session, identity, project_id, write=True)
    return await _submit_operation(
        session,
        response,
        identity,
        project,
        kind="compile",
        payload={"project_id": project_id},
        idempotency_key=idempotency_key,
    )


@router.get("/projects/{project_id}/builds", response_model=list[BuildOut])
async def list_builds(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[Build]:
    await scoped_project(session, identity, project_id)
    return list(
        (
            await session.scalars(
                select(Build)
                .where(Build.project_id == project_id)
                .order_by(Build.created_at.desc())
            )
        ).all()
    )


@router.get("/builds/{build_id}", response_model=BuildOut)
async def get_build(
    build_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Build:
    return await scoped_build(session, identity, build_id)


@router.get("/builds/{build_id}/artifacts/{artifact_path:path}")
async def get_artifact(
    build_id: str,
    artifact_path: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Any:
    build = await scoped_build(session, identity, build_id)
    if artifact_path not in build.artifacts:
        raise ServiceError("artifact_not_found", "Build artifact not found.", status_code=404)
    value = build.artifacts[artifact_path]
    media_type = {
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".md": "text/markdown",
    }.get("." + artifact_path.rsplit(".", 1)[-1] if "." in artifact_path else "")
    return Response(content=artifact_bytes(value), media_type=media_type)


@router.get("/projects/{project_id}/test-cases", response_model=list[TestCaseOut])
async def list_tests(
    project_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[TestCase]:
    await scoped_project(session, identity, project_id)
    return list(
        (
            await session.scalars(
                select(TestCase)
                .where(TestCase.project_id == project_id)
                .order_by(TestCase.stable_key)
            )
        ).all()
    )


@router.post(
    "/projects/{project_id}/test-generation-jobs",
    response_model=OperationOut,
    status_code=202,
)
async def generate_tests(
    project_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> OperationOut:
    project = await scoped_project(session, identity, project_id, write=True)
    return await _submit_operation(
        session,
        response,
        identity,
        project,
        kind="test_generation",
        payload={"project_id": project_id},
        idempotency_key=idempotency_key,
    )


@router.patch("/test-cases/{test_case_id}", response_model=TestCaseOut)
async def patch_test(
    test_case_id: str,
    payload: TestCasePatch,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> TestCase:
    test = await scoped_test(session, identity, test_case_id, write=True)
    test.review_status = payload.review_status
    await session.commit()
    await session.refresh(test)
    return test


@router.post("/projects/{project_id}/runs", response_model=OperationOut, status_code=202)
async def create_run(
    project_id: str,
    response: Response,
    payload: RunCreate | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> OperationOut:
    project = await scoped_project(session, identity, project_id, write=True)
    build_id = payload.build_id if payload else None
    if build_id:
        build = await scoped_build(session, identity, str(build_id))
        if build.project_id != project_id:
            raise ServiceError("build_not_found", "Build not found.", status_code=404)
    job_payload = {"project_id": project_id, "adapter": "fixture", "build_id": build_id}
    return await _submit_operation(
        session,
        response,
        identity,
        project,
        kind="run",
        payload=job_payload,
        idempotency_key=idempotency_key,
    )


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(
    run_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Run:
    return await scoped_run(session, identity, run_id)


@router.get("/runs/{run_id}/results")
async def get_results(
    run_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    await scoped_run(session, identity, run_id)
    rows = list(
        (
            await session.scalars(
                select(ScenarioResult)
                .where(ScenarioResult.run_id == run_id)
                .order_by(ScenarioResult.test_case_id, ScenarioResult.arm)
            )
        ).all()
    )
    return [
        {
            **ScenarioResultOut.model_validate(row).model_dump(mode="json"),
            "test": row.test_snapshot,
        }
        for row in rows
    ]


@router.get("/scenario-results/{result_id}/trace")
async def get_trace(
    result_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await scoped_result(session, identity, result_id)
    await scoped_run(session, identity, result.run_id)
    events = list(
        (
            await session.scalars(
                select(TraceEventModel)
                .where(TraceEventModel.result_id == result_id)
                .order_by(TraceEventModel.sequence)
            )
        ).all()
    )
    return {
        "result": ScenarioResultOut.model_validate(result).model_dump(mode="json"),
        "test": result.test_snapshot,
        "events": [
            {
                "id": event.id,
                "sequence": event.sequence,
                "type": event.type,
                "payload": event.payload,
                "rule_ids": event.rule_ids,
                "duration_ms": event.duration_ms,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


@router.post("/runs/{run_id}/reports", response_model=ReportOut, status_code=201)
async def make_report(
    run_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Report:
    await scoped_run(session, identity, run_id, write=True)
    return await create_report(session, run_id)


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Report:
    return await scoped_report(session, identity, report_id)


@router.get("/runs/{run_id}/reports", response_model=list[ReportOut])
async def list_reports(
    run_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[Report]:
    await scoped_run(session, identity, run_id)
    return list(
        (
            await session.scalars(
                select(Report).where(Report.run_id == run_id).order_by(Report.created_at.desc())
            )
        ).all()
    )


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    format: str = Query(pattern="^(markdown|json)$"),
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> Any:
    report = await scoped_report(session, identity, report_id)
    filename = f"aletheia-report-{report.id[:8]}"
    if format == "markdown":
        return Response(
            content=report.rendered_markdown.encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )
    return Response(
        content=canonical_json_bytes(report.evidence),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@router.get("/jobs/{job_id}", response_model=OperationOut)
async def get_job(
    job_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> OperationOut:
    job = await scoped_job(session, identity, job_id)
    if get_settings().demo_inline_jobs:
        job = await expire_stale_inline_operation(session, job)
    return operation_out(job)
