from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from app.schemas import (
    BuildOut,
    DocumentOut,
    FindingOut,
    FindingPatch,
    ProjectOut,
    ReportOut,
    RuleOut,
    RulePatch,
    RunOut,
    ScenarioResultOut,
    TestCaseOut,
)
from app.services.canonical import text_hash, token_estimate
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.ingestion import parse_document
from app.services.reporting import create_report
from app.services.review import resolve_finding, revise_rule
from app.services.runner import run_comparison
from app.services.seed import seed_demo

router = APIRouter(prefix="/api/v1")


async def _project(session: AsyncSession, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    return project


async def _job(session: AsyncSession, kind: str, payload: dict[str, Any]) -> Job:
    inline = get_settings().demo_inline_jobs
    job = Job(
        kind=kind,
        payload=payload,
        status="running" if inline else "queued",
        progress=5 if inline else 0,
        attempt_count=1 if inline else 0,
        owner="inline-demo" if inline else None,
    )
    session.add(job)
    await session.flush()
    return job


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


@router.post("/demo/reset", response_model=ProjectOut)
async def reset_demo(
    x_demo_reset_secret: str | None = Header(default=None), session: AsyncSession = Depends(get_session)
) -> Project:
    settings = get_settings()
    if not settings.demo_mode:
        raise ServiceError("demo_reset_disabled", "Demo reset is disabled in this environment.", status_code=403)
    if settings.demo_reset_secret and x_demo_reset_secret != settings.demo_reset_secret:
        raise ServiceError("demo_reset_forbidden", "A valid reset secret is required.", status_code=403)
    return await seed_demo(session, reset=True)


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[Project]:
    return list((await session.scalars(select(Project).order_by(Project.created_at))).all())


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(payload: dict[str, Any], session: AsyncSession = Depends(get_session)) -> Project:
    required = {"slug", "name"}
    if not required.issubset(payload):
        raise ServiceError("invalid_project", "Project slug and name are required.")
    project = Project(slug=str(payload["slug"]), name=str(payload["name"]), domain=str(payload.get("domain", "retail")), description=str(payload.get("description", "")), mode="local")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, session: AsyncSession = Depends(get_session)) -> Project:
    return await _project(session, project_id)


@router.get("/projects/{project_id}/summary")
async def project_summary(project_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    await _project(session, project_id)
    async def count(model: Any, *conditions: Any) -> int:
        return int(await session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id, *conditions)) or 0)
    current_build = await session.scalar(select(Build).where(Build.project_id == project_id).order_by(Build.created_at.desc()))
    last_run = await session.scalar(select(Run).where(Run.project_id == project_id).order_by(Run.started_at.desc()))
    return {
        "sources": await count(Document),
        "approved_rules": await count(Rule, Rule.status == "approved"),
        "critical_findings": await count(Finding, Finding.severity == "critical", Finding.resolution_state == "open"),
        "tests": await count(TestCase, TestCase.review_status == "approved"),
        "current_build": BuildOut.model_validate(current_build).model_dump(mode="json") if current_build else None,
        "last_run": RunOut.model_validate(last_run).model_dump(mode="json") if last_run else None,
    }


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
async def list_documents(project_id: str, session: AsyncSession = Depends(get_session)) -> list[Document]:
    await _project(session, project_id)
    return list((await session.scalars(select(Document).where(Document.project_id == project_id).order_by(Document.created_at))).all())


@router.post("/projects/{project_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    name: str | None = Form(default=None),
    kind: str = Form(default="policy"),
    session: AsyncSession = Depends(get_session),
) -> Document:
    await _project(session, project_id)
    settings = get_settings()
    if settings.demo_mode:
        raise ServiceError("uploads_disabled_in_demo", "Uploads are disabled in the hosted-style demo. Use local mode for non-confidential test documents.", status_code=403)
    if file:
        raw = await file.read(settings.upload_max_bytes + 1)
        normalized, mime, provenance = parse_document(file.filename or "upload.txt", raw, max_bytes=settings.upload_max_bytes)
        document_name = file.filename or "upload.txt"
    elif text is not None:
        raw = text.encode()
        if len(raw) > settings.upload_max_bytes:
            raise ServiceError("file_too_large", "Pasted text exceeds the upload limit.")
        normalized, mime, provenance, document_name = text.replace("\r\n", "\n"), "text/plain", {"locator": "normalized_line"}, name or "pasted-source.txt"
    else:
        raise ServiceError("document_required", "Choose a file or paste text.")
    version = int(await session.scalar(select(func.count()).select_from(Document).where(Document.project_id == project_id, Document.name == document_name)) or 0) + 1
    document = Document(project_id=project_id, kind=kind, name=document_name, version=version, original_sha256=text_hash(normalized), normalized_text=normalized, mime_type=mime, line_count=len(normalized.splitlines()), token_estimate=token_estimate(normalized), origin={"type": "upload", **provenance})
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, session: AsyncSession = Depends(get_session)) -> Document:
    document = await session.get(Document, document_id)
    if not document:
        raise ServiceError("document_not_found", "Document not found.", status_code=404)
    return document


@router.post("/projects/{project_id}/analysis-jobs")
async def analyze_project(project_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    await _project(session, project_id)
    job = await _job(session, "analyze", {"project_id": project_id, "extractor": "fixture"})
    if not get_settings().demo_inline_jobs:
        await session.commit()
        return {"job_id": job.id, "status": "queued", "extractor": "fixture"}
    job.status, job.progress, job.resource_id = "succeeded", 100, project_id
    await session.commit()
    return {"job_id": job.id, "status": job.status, "extractor": "fixture", "note": "Checked-in candidates were quote-verified during seed."}


@router.get("/projects/{project_id}/rules", response_model=list[RuleOut])
async def list_rules(project_id: str, session: AsyncSession = Depends(get_session)) -> list[Rule]:
    await _project(session, project_id)
    return list((await session.scalars(select(Rule).where(Rule.project_id == project_id, Rule.status != "superseded").order_by(Rule.severity.desc(), Rule.title))).all())


@router.get("/rules/{rule_id}", response_model=RuleOut)
async def get_rule(rule_id: str, session: AsyncSession = Depends(get_session)) -> Rule:
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise ServiceError("rule_not_found", "Rule not found.", status_code=404)
    return rule


@router.patch("/rules/{rule_id}", response_model=RuleOut)
async def patch_rule(rule_id: str, payload: RulePatch, session: AsyncSession = Depends(get_session)) -> Rule:
    return await revise_rule(session, rule_id, expected_revision=payload.expected_revision, changes=payload.model_dump(exclude={"expected_revision"}, exclude_none=True))


@router.post("/rules/{rule_id}/approve", response_model=RuleOut)
async def approve_rule(rule_id: str, payload: dict[str, Any] | None = None, session: AsyncSession = Depends(get_session)) -> Rule:
    current = await session.get(Rule, rule_id)
    if not current:
        raise ServiceError("rule_not_found", "Rule not found.", status_code=404)
    expected = int((payload or {}).get("expected_revision", current.revision))
    return await revise_rule(session, rule_id, expected_revision=expected, changes={"reviewer_note": (payload or {}).get("reviewer_note", "Approved after source and boundary review.")}, status="approved")


@router.post("/rules/{rule_id}/reject", response_model=RuleOut)
async def reject_rule(rule_id: str, payload: dict[str, Any] | None = None, session: AsyncSession = Depends(get_session)) -> Rule:
    current = await session.get(Rule, rule_id)
    if not current:
        raise ServiceError("rule_not_found", "Rule not found.", status_code=404)
    expected = int((payload or {}).get("expected_revision", current.revision))
    return await revise_rule(session, rule_id, expected_revision=expected, changes={"reviewer_note": (payload or {}).get("reviewer_note", "Rejected during policy review.")}, status="rejected")


@router.get("/projects/{project_id}/findings", response_model=list[FindingOut])
async def list_findings(project_id: str, session: AsyncSession = Depends(get_session)) -> list[Finding]:
    await _project(session, project_id)
    return list((await session.scalars(select(Finding).where(Finding.project_id == project_id).order_by(Finding.severity.desc(), Finding.created_at))).all())


@router.patch("/findings/{finding_id}", response_model=FindingOut)
async def patch_finding(finding_id: str, payload: FindingPatch, session: AsyncSession = Depends(get_session)) -> Finding:
    return await resolve_finding(session, finding_id, payload.resolution_state, payload.resolution_note)


@router.post("/projects/{project_id}/builds", response_model=BuildOut, status_code=201)
async def create_build(project_id: str, session: AsyncSession = Depends(get_session)) -> Any:
    await _project(session, project_id)
    job = await _job(session, "compile", {"project_id": project_id})
    if not get_settings().demo_inline_jobs:
        await session.commit()
        return JSONResponse(status_code=202, content={"job_id": job.id, "status": "queued"})
    try:
        build = await compile_project(session, project_id)
        current_job = await session.get(Job, job.id)
        if current_job:
            current_job.status, current_job.progress, current_job.resource_id = "succeeded", 100, build.id
            await session.commit()
        return build
    except ServiceError as error:
        job.status, job.error_code, job.error_message = "failed", error.code, error.message
        await session.commit()
        raise


@router.get("/projects/{project_id}/builds", response_model=list[BuildOut])
async def list_builds(project_id: str, session: AsyncSession = Depends(get_session)) -> list[Build]:
    return list((await session.scalars(select(Build).where(Build.project_id == project_id).order_by(Build.created_at.desc()))).all())


@router.get("/builds/{build_id}", response_model=BuildOut)
async def get_build(build_id: str, session: AsyncSession = Depends(get_session)) -> Build:
    build = await session.get(Build, build_id)
    if not build:
        raise ServiceError("build_not_found", "Build not found.", status_code=404)
    return build


@router.get("/builds/{build_id}/artifacts/{artifact_path:path}")
async def get_artifact(build_id: str, artifact_path: str, session: AsyncSession = Depends(get_session)) -> Any:
    build = await session.get(Build, build_id)
    if not build or artifact_path not in build.artifacts:
        raise ServiceError("artifact_not_found", "Build artifact not found.", status_code=404)
    value = build.artifacts[artifact_path]
    if isinstance(value, str):
        return PlainTextResponse(value)
    return JSONResponse(value)


@router.get("/projects/{project_id}/test-cases", response_model=list[TestCaseOut])
async def list_tests(project_id: str, session: AsyncSession = Depends(get_session)) -> list[TestCase]:
    return list((await session.scalars(select(TestCase).where(TestCase.project_id == project_id).order_by(TestCase.stable_key))).all())


@router.post("/projects/{project_id}/test-generation-jobs")
async def generate_tests(project_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    job = await _job(session, "test_generation", {"project_id": project_id})
    if not get_settings().demo_inline_jobs:
        await session.commit()
        return {"job_id": job.id, "status": "queued", "test_count": 0}
    count = int(await session.scalar(select(func.count()).select_from(TestCase).where(TestCase.project_id == project_id)) or 0)
    job.status, job.progress, job.resource_id = "succeeded", 100, project_id
    await session.commit()
    return {"job_id": job.id, "status": "succeeded", "test_count": count}


@router.patch("/test-cases/{test_case_id}", response_model=TestCaseOut)
async def patch_test(test_case_id: str, payload: dict[str, Any], session: AsyncSession = Depends(get_session)) -> TestCase:
    test = await session.get(TestCase, test_case_id)
    if not test:
        raise ServiceError("test_not_found", "Test case not found.", status_code=404)
    if "review_status" in payload:
        test.review_status = str(payload["review_status"])
    await session.commit()
    await session.refresh(test)
    return test


@router.post("/projects/{project_id}/runs", response_model=RunOut, status_code=201)
async def create_run(project_id: str, payload: dict[str, Any] | None = None, session: AsyncSession = Depends(get_session)) -> Any:
    job_payload = {
        "project_id": project_id,
        "adapter": "fixture",
        "build_id": (payload or {}).get("build_id"),
    }
    job = await _job(session, "run", job_payload)
    if not get_settings().demo_inline_jobs:
        await session.commit()
        return JSONResponse(status_code=202, content={"job_id": job.id, "status": "queued"})
    try:
        run = await run_comparison(session, project_id, (payload or {}).get("build_id"))
        current_job = await session.get(Job, job.id)
        if current_job:
            current_job.status, current_job.progress, current_job.resource_id = "succeeded", 100, run.id
            await session.commit()
        return run
    except ServiceError as error:
        job.status, job.error_code, job.error_message = "failed", error.code, error.message
        await session.commit()
        raise


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> Run:
    run = await session.get(Run, run_id)
    if not run:
        raise ServiceError("run_not_found", "Run not found.", status_code=404)
    return run


@router.get("/runs/{run_id}/results")
async def get_results(run_id: str, session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    rows = list((await session.scalars(select(ScenarioResult).where(ScenarioResult.run_id == run_id).order_by(ScenarioResult.test_case_id, ScenarioResult.arm))).all())
    tests = {test.id: test for test in (await session.scalars(select(TestCase).where(TestCase.id.in_([row.test_case_id for row in rows])))).all()} if rows else {}
    return [{**ScenarioResultOut.model_validate(row).model_dump(mode="json"), "test": {"stable_key": tests[row.test_case_id].stable_key, "title": tests[row.test_case_id].title, "rule_ids": tests[row.test_case_id].spec.get("rule_ids", []), "tags": tests[row.test_case_id].spec.get("tags", [])}} for row in rows]


@router.get("/scenario-results/{result_id}/trace")
async def get_trace(result_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    result = await session.get(ScenarioResult, result_id)
    if not result:
        raise ServiceError("result_not_found", "Scenario result not found.", status_code=404)
    test = await session.get(TestCase, result.test_case_id)
    events = list((await session.scalars(select(TraceEventModel).where(TraceEventModel.result_id == result_id).order_by(TraceEventModel.sequence))).all())
    return {
        "result": ScenarioResultOut.model_validate(result).model_dump(mode="json"),
        "test": TestCaseOut.model_validate(test).model_dump(mode="json") if test else None,
        "events": [{"id": event.id, "sequence": event.sequence, "type": event.type, "payload": event.payload, "rule_ids": event.rule_ids, "duration_ms": event.duration_ms, "created_at": event.created_at} for event in events],
    }


@router.post("/runs/{run_id}/reports", response_model=ReportOut, status_code=201)
async def make_report(run_id: str, session: AsyncSession = Depends(get_session)) -> Report:
    return await create_report(session, run_id)


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(report_id: str, session: AsyncSession = Depends(get_session)) -> Report:
    report = await session.get(Report, report_id)
    if not report:
        raise ServiceError("report_not_found", "Report not found.", status_code=404)
    return report


@router.get("/runs/{run_id}/reports", response_model=list[ReportOut])
async def list_reports(run_id: str, session: AsyncSession = Depends(get_session)) -> list[Report]:
    return list((await session.scalars(select(Report).where(Report.run_id == run_id).order_by(Report.created_at.desc()))).all())


@router.get("/reports/{report_id}/export")
async def export_report(report_id: str, format: str = Query(pattern="^(markdown|json)$"), session: AsyncSession = Depends(get_session)) -> Any:
    report = await session.get(Report, report_id)
    if not report:
        raise ServiceError("report_not_found", "Report not found.", status_code=404)
    if format == "markdown":
        return PlainTextResponse(report.rendered_markdown, headers={"Content-Disposition": f'attachment; filename="aletheia-report-{report.id[:8]}.md"'})
    return JSONResponse(report.evidence, headers={"Content-Disposition": f'attachment; filename="aletheia-report-{report.id[:8]}.json"'})


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    job = await session.get(Job, job_id)
    if not job:
        raise ServiceError("job_not_found", "Job not found.", status_code=404)
    return {"id": job.id, "kind": job.kind, "status": job.status, "progress": job.progress, "resource_id": job.resource_id, "attempt_count": job.attempt_count, "error": {"code": job.error_code, "message": job.error_message} if job.error_code else None, "updated_at": job.updated_at}
