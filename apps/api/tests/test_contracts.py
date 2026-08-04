from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, Project, Rule
from app.schemas import (
    BuildManifest,
    EvidenceReport,
    FactFixture,
    PolicyArtifact,
    RegressionArtifact,
    ToolRegistry,
)
from app.schemas import TestCaseSpec as CaseSpecContract
from app.services.compiler import compile_project
from app.services.reporting import create_report
from app.services.review import resolve_finding, revise_rule
from app.services.runner import run_comparison
from app.services.seed import DEMO_DIR
from app.services.seed import test_specs as northstar_test_specs


async def _prepare_project(session: AsyncSession) -> Project:
    project = await session.scalar(
        select(Project).where(Project.slug == "northstar-retail")
    )
    assert project is not None
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
            rule for rule in related if rule.stable_key.startswith("rule.legacy.")
        )
        await resolve_finding(
            session,
            finding.id,
            "resolved",
            "The current policy is authoritative for this fixture.",
            winner_rule_id=winner.id,
            loser_rule_id=loser.id,
            authority="Refund Policy v3",
            actor="contract-test",
        )
    threshold = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.refund.approval_threshold",
            Rule.status == "needs_review",
        )
    )
    assert threshold is not None
    await revise_rule(
        session,
        threshold.id,
        expected_revision=threshold.revision,
        changes={"reviewer_note": "Strict greater-than boundary verified."},
        status="approved",
    )
    return project


def test_seeded_test_contract_round_trips_without_dropping_fields() -> None:
    for spec in northstar_test_specs():
        validated = CaseSpecContract.model_validate(spec)
        assert validated.model_dump(mode="json", by_alias=True) == spec


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("messages", 0, "unexpected"), True),
        (("expected", "unexpected"), True),
        (("scripted_trajectories", "compiled_enforced", 0, "unexpected"), True),
    ],
)
def test_test_contract_rejects_unknown_nested_fields(
    path: tuple[str | int, ...], value: object
) -> None:
    candidate = deepcopy(northstar_test_specs()[0])
    target: object = candidate
    for part in path[:-1]:
        assert isinstance(target, (dict, list))
        target = target[part]  # type: ignore[index]
    assert isinstance(target, dict)
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        CaseSpecContract.model_validate(candidate)


@pytest.mark.asyncio
async def test_runtime_build_and_evidence_contracts_round_trip_exactly(
    session: AsyncSession,
) -> None:
    project = await _prepare_project(session)
    build = await compile_project(session, project.id)

    manifest = json.loads(build.artifacts["manifest.json"])
    assert (
        BuildManifest.model_validate(manifest).model_dump(mode="json", by_alias=True)
        == manifest
    )
    policy = json.loads(build.artifacts["policies/tool-policy.json"])
    assert (
        PolicyArtifact.model_validate(policy).model_dump(mode="json", by_alias=True)
        == policy
    )

    import yaml

    regression = yaml.safe_load(build.artifacts["tests/regression.yaml"])
    assert (
        RegressionArtifact.model_validate(regression).model_dump(
            mode="json", by_alias=True
        )
        == regression
    )

    run = await run_comparison(session, project.id, build.id)
    report = await create_report(session, run.id)
    assert (
        EvidenceReport.model_validate(report.evidence).model_dump(
            mode="json", by_alias=True
        )
        == report.evidence
    )


def test_manifest_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BuildManifest.model_validate(
            {
                "schema_version": "0.3",
                "compiler_version": "0.2.0",
                "unexpected": True,
            }
        )


def test_tool_and_fact_contracts_round_trip_exact_fixture_bytes() -> None:
    tools = json.loads((DEMO_DIR / "tools.json").read_text(encoding="utf-8"))
    facts = json.loads((DEMO_DIR / "orders.json").read_text(encoding="utf-8"))
    assert (
        ToolRegistry.model_validate(tools).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        == tools
    )
    assert (
        FactFixture.model_validate(facts).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        == facts
    )


def test_tool_and_fact_contracts_reject_unknown_or_ambiguous_values() -> None:
    tools = json.loads((DEMO_DIR / "tools.json").read_text(encoding="utf-8"))
    tools["tools"][0]["unexpected"] = True
    with pytest.raises(ValidationError):
        ToolRegistry.model_validate(tools)

    facts = json.loads((DEMO_DIR / "orders.json").read_text(encoding="utf-8"))
    facts["orders"][0]["amount"] = {"currency": "USD", "minor_units": 1.5}
    with pytest.raises(ValidationError):
        FactFixture.model_validate(facts)

    facts = json.loads((DEMO_DIR / "orders.json").read_text(encoding="utf-8"))
    facts["evaluation_timestamp"] = "2026-08-03T12:00:00"
    with pytest.raises(ValidationError):
        FactFixture.model_validate(facts)
