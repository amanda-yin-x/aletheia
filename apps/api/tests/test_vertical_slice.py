import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Finding, Project, Rule, ScenarioResult, TraceEventModel
from app.models import TestCase as CaseModel
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.ingestion import parse_document
from app.services.reporting import EVIDENCE_BOUNDARY, create_report, release_gate_ready
from app.services.review import resolve_finding, revise_rule
from app.services.runner import run_comparison
from app.services.seed import seed_demo


async def prepare(session: AsyncSession) -> Project:
    project = await session.scalar(select(Project).where(Project.slug == "northstar-retail"))
    assert project
    findings = list((await session.scalars(select(Finding).where(Finding.project_id == project.id, Finding.severity == "critical"))).all())
    for finding in findings:
        related = list(
            (
                await session.scalars(
                    select(Rule).where(Rule.id.in_(finding.related_rule_ids))
                )
            ).all()
        )
        winner = next(
            rule for rule in related if not rule.stable_key.startswith("rule.legacy.")
        )
        loser = next(
            rule for rule in related if rule.stable_key.startswith("rule.legacy.")
        )
        await resolve_finding(
            session,
            finding.id,
            "resolved",
            "Current policy v3 is authoritative.",
            winner_rule_id=winner.id,
            loser_rule_id=loser.id,
            authority="Refund Policy v3",
            actor="vertical-slice-test",
        )
    threshold = await session.scalar(select(Rule).where(Rule.project_id == project.id, Rule.stable_key == "rule.refund.approval_threshold", Rule.status == "needs_review"))
    assert threshold
    await revise_rule(session, threshold.id, expected_revision=threshold.revision, changes={"reviewer_note": "Strict > boundary verified."}, status="approved")
    return project


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_quotes_are_exact(session: AsyncSession) -> None:
    first = await seed_demo(session)
    second = await seed_demo(session)
    assert first.id == second.id
    assert await session.scalar(select(func.count()).select_from(CaseModel)) == 16
    cases = list((await session.scalars(select(CaseModel))).all())
    assert {case.provenance for case in cases} == {"Aletheia-authored"}
    assert {case.spec["provenance"] for case in cases} == {"aletheia_authored_v1"}
    composite = next(case for case in cases if case.stable_key == "refund.nonreturnable")
    proposal = composite.spec["scripted_trajectories"]["compiled_enforced"][0]
    assert composite.title == (
        "Customer requests a $249 gift-card refund for non-returnable order N-1099"
    )
    assert proposal["name"] == "issue_refund"
    assert proposal["arguments"] == {
        "order_id": "N-1099",
        "item_id": "I-99",
        "amount": {"currency": "USD", "minor_units": 24900},
        "destination": "gift_card",
    }
    assert set(composite.spec["rule_ids"]) == {
        "rule.refund.returnability",
        "rule.refund.destination",
        "rule.refund.approval_threshold",
    }
    documents = {doc.id: doc for doc in (await session.scalars(select(Document))).all()}
    assert {document.origin["data_scope"] for document in documents.values()} == {"evaluation"}
    assert {document.origin["type"] for document in documents.values()} == {"aletheia_authored"}
    rules = list((await session.scalars(select(Rule).where(Rule.status != "superseded"))).all())
    for rule in rules:
        assert rule.source_refs
        for ref in rule.source_refs:
            document = documents[ref["document_id"]]
            span = "\n".join(document.normalized_text.splitlines()[ref["line_start"] - 1 : ref["line_end"]])
            assert span == ref["quote"]
            assert ref["source_sha256"] == document.original_sha256


@pytest.mark.asyncio
async def test_critical_findings_block_compilation(session: AsyncSession) -> None:
    project = await session.scalar(select(Project).where(Project.slug == "northstar-retail"))
    assert project
    with pytest.raises(ServiceError, match="Resolve critical policy conflicts") as error:
        await compile_project(session, project.id)
    assert error.value.code == "critical_findings_unresolved"


@pytest.mark.asyncio
async def test_complete_no_key_workflow_and_boundary_trace(session: AsyncSession) -> None:
    project = await prepare(session)
    build = await compile_project(session, project.id)
    assert build.stats["original"]["lines"] > build.stats["candidate"]["lines"]
    assert len(json.loads(build.artifacts["policies/tool-policy.json"])["rules"]) == 7
    assert set(build.source_map) >= {"prompt-kernel.md", "policies/tool-policy.json", "tests/regression.yaml"}
    run = await run_comparison(session, project.id, build.id)
    assert run.metrics["compiled_enforced"]["executed_violation_rate"] == 0
    assert run.metrics["compiled_enforced"]["false_block_rate"] == 0
    assert run.metrics["coverage"]["test_count"] == 16
    assert run.metrics["coverage"]["rule_coverage"]["ratio"] == 1
    assert run.metrics["coverage"]["source_coverage"]["ratio"] == 1
    assert run.metrics["coverage"]["boundary_coverage"]["ratio"] == 1
    assert run.metrics["coverage"]["critical_unclassified_rules"] == []
    assert run.dataset_manifest["data_scope"] == "evaluation"
    assert release_gate_ready(run.metrics, run.dataset_manifest)
    incomplete_metrics = {**run.metrics, "compiled_enforced": {**run.metrics["compiled_enforced"], "task_success_rate": 0.9375}}
    assert not release_gate_ready(incomplete_metrics, run.dataset_manifest)
    case = await session.scalar(select(CaseModel).where(CaseModel.stable_key == "refund.amount.200_01.no_approval"))
    assert case
    guarded = await session.scalar(select(ScenarioResult).where(ScenarioResult.run_id == run.id, ScenarioResult.test_case_id == case.id, ScenarioResult.arm == "compiled_enforced"))
    baseline = await session.scalar(select(ScenarioResult).where(ScenarioResult.run_id == run.id, ScenarioResult.test_case_id == case.id, ScenarioResult.arm == "baseline_unenforced"))
    assert guarded and baseline
    assert guarded.metrics["executed_calls"] == 0
    assert guarded.metrics["blocked_calls"] == 1
    assert baseline.metrics["executed_violation"] is True
    composite_case = await session.scalar(
        select(CaseModel).where(CaseModel.stable_key == "refund.nonreturnable")
    )
    assert composite_case
    composite_guarded = await session.scalar(
        select(ScenarioResult).where(
            ScenarioResult.run_id == run.id,
            ScenarioResult.test_case_id == composite_case.id,
            ScenarioResult.arm == "compiled_enforced",
        )
    )
    composite_baseline = await session.scalar(
        select(ScenarioResult).where(
            ScenarioResult.run_id == run.id,
            ScenarioResult.test_case_id == composite_case.id,
            ScenarioResult.arm == "baseline_unenforced",
        )
    )
    assert composite_guarded and composite_baseline
    assert composite_guarded.metrics["blocked_calls"] == 1
    assert composite_guarded.metrics["executed_calls"] == 0
    assert composite_baseline.metrics["executed_violation"] is True
    decision_event = await session.scalar(
        select(TraceEventModel).where(
            TraceEventModel.result_id == composite_guarded.id,
            TraceEventModel.type == "policy_evaluated",
        )
    )
    assert decision_event
    assert decision_event.payload["decision"] == "deny"
    assert set(decision_event.rule_ids) == {
        "rule.refund.returnability",
        "rule.refund.destination",
    }
    assert len(decision_event.payload["decision_hash"]) == 64
    guarded_event_types = set(
        (
            await session.scalars(
                select(TraceEventModel.type).where(
                    TraceEventModel.result_id == composite_guarded.id
                )
            )
        ).all()
    )
    baseline_event_types = set(
        (
            await session.scalars(
                select(TraceEventModel.type).where(
                    TraceEventModel.result_id == composite_baseline.id
                )
            )
        ).all()
    )
    assert "tool_executed" not in guarded_event_types
    assert "state_changed" not in guarded_event_types
    assert {"policy_evaluated", "tool_executed", "state_changed"} <= baseline_event_types
    report = await create_report(session, run.id)
    assert report.verdict == "Fixture suite passed"
    assert report.evidence["evidence_boundary"] == EVIDENCE_BOUNDARY
    assert report.evidence["provenance"]["data_scope"] == "Evaluation fixture — no customer records"
    assert report.evidence["provenance"]["adapter"] == "Deterministic replay"
    assert report.evidence["schema_version"] == "0.3"
    assert report.evidence["provenance"]["evaluation_timestamp"].endswith("Z")
    assert "Aletheia-authored refund boundary suite" in report.rendered_markdown
    assert len(report.content_hash) == 64
    assert "not a safety, security, or compliance certification" in report.rendered_markdown.lower()


def test_ingestion_accepts_safe_formats_and_rejects_unsafe() -> None:
    text, mime, _ = parse_document("policy.yaml", b"window: 30\napproval: 200\n")
    assert text.startswith("window") and mime == "application/yaml"
    with pytest.raises(ServiceError) as unsupported:
        parse_document("payload.zip", b"PK")
    assert unsupported.value.code == "unsupported_file_type"
    with pytest.raises(ServiceError) as too_large:
        parse_document("policy.md", b"x" * 11, max_bytes=10)
    assert too_large.value.code == "file_too_large"


def test_demo_corpus_has_meaningful_baseline() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "demo" / "northstar-retail" / "baseline-system-prompt.md"
    text = path.read_text()
    assert 150 <= len(text.splitlines()) <= 260
    assert "Refunds over $200 require supervisor approval" in text
    assert "Never describe a proposed call as an executed call" in text
