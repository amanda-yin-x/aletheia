from __future__ import annotations

import asyncio
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app
from app.models import (
    Finding,
    Rule,
    ScenarioResult,
    UserAccount,
    Workspace,
    WorkspaceMembership,
)
from app.models import TestCase as CaseModel
from app.services.canonical import (
    artifact_bytes,
    bytes_hash,
    canonical_json_bytes,
)
from app.services.compiler import ROOT_ARTIFACT, compile_project
from app.services.reporting import create_report
from app.services.review import resolve_finding, revise_rule
from app.services.runner import run_comparison, run_scenario
from app.services.seed import DEMO_DIR, seed_demo
from app.services.seed import test_specs as northstar_test_specs

DRAFT_2020_12_URI = "https://json-schema.org/draft/2020-12/schema"


async def _make_buildable(session: AsyncSession, project_id: str) -> None:
    findings = list(
        (
            await session.scalars(
                select(Finding).where(
                    Finding.project_id == project_id,
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
            actor="reproducibility-test",
        )
    threshold = await session.scalar(
        select(Rule).where(
            Rule.project_id == project_id,
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


async def _second_seeded_project(session: AsyncSession) -> str:
    user = UserAccount(id="reproducibility-user", email="repro@example.test")
    workspace = Workspace(
        id="10000000-0000-0000-0000-000000000002",
        slug="reproducibility-workspace",
        name="Reproducibility workspace",
        created_by_user_id=user.id,
    )
    session.add_all([user, workspace])
    await session.flush()
    session.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
    )
    await session.commit()
    project = await seed_demo(session, workspace_id=workspace.id)
    return project.id


def _compile_in_fresh_process(database_path: str) -> tuple[str, dict[str, bytes]]:
    """Build from a fresh interpreter so process-local caches cannot affect bytes."""

    async def run() -> tuple[str, dict[str, bytes]]:
        from app.db import Base

        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as child_session:
                project = await seed_demo(child_session)
                await _make_buildable(child_session, project.id)
                build = await compile_project(child_session, project.id)
                return build.content_hash, {
                    name: artifact_bytes(value)
                    for name, value in sorted(build.artifacts.items())
                }
        finally:
            await engine.dispose()

    return asyncio.run(run())


@pytest.mark.asyncio
async def test_fresh_equivalent_builds_have_identical_byte_roots(
    session: AsyncSession,
) -> None:
    first = await seed_demo(session)
    second_id = await _second_seeded_project(session)
    await _make_buildable(session, first.id)
    await _make_buildable(session, second_id)

    first_build = await compile_project(session, first.id)
    second_build = await compile_project(session, second_id)

    assert first_build.id != second_build.id
    assert first_build.content_hash == second_build.content_hash
    assert first_build.artifacts == second_build.artifacts
    first_manifest = json.loads(first_build.artifacts[ROOT_ARTIFACT])
    second_manifest = json.loads(second_build.artifacts[ROOT_ARTIFACT])
    assert first_manifest["artifact_hashes"] == second_manifest["artifact_hashes"]
    assert first_manifest["artifact_root"]["excluded"] == [ROOT_ARTIFACT]
    assert set(first_manifest["artifact_hashes"]) == set(first_build.artifacts) - {
        ROOT_ARTIFACT
    }
    assert bytes_hash(artifact_bytes(first_build.artifacts[ROOT_ARTIFACT])) == (
        first_build.content_hash
    )
    for path, expected in first_manifest["artifact_hashes"].items():
        # artifact_bytes is also the exact helper used by download responses.
        assert bytes_hash(artifact_bytes(first_build.artifacts[path])) == expected

    async def override_session():  # type: ignore[no-untyped-def]
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path, expected in first_manifest["artifact_hashes"].items():
                download = await client.get(
                    f"/api/v1/builds/{first_build.id}/artifacts/{path}"
                )
                assert download.status_code == 200
                assert download.content == artifact_bytes(first_build.artifacts[path])
                assert bytes_hash(download.content) == expected
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_equivalent_builds_are_byte_identical_across_fresh_processes(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
        futures = [
            pool.submit(_compile_in_fresh_process, str(tmp_path / f"process-{index}.db"))
            for index in range(2)
        ]
        first, second = [future.result(timeout=30) for future in futures]

    assert first[0] == second[0]
    assert first[1] == second[1]
    assert bytes_hash(first[1][ROOT_ARTIFACT]) == first[0]


@pytest.mark.asyncio
async def test_build_pinned_run_ignores_mutable_rule_and_test_rows(
    session: AsyncSession,
) -> None:
    project = await seed_demo(session)
    await _make_buildable(session, project.id)
    build = await compile_project(session, project.id)
    before = await run_comparison(session, project.id, build.id)

    current_rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.refund.window",
            Rule.status == "approved",
        )
    )
    current_test = await session.scalar(
        select(CaseModel).where(
            CaseModel.project_id == project.id,
            CaseModel.stable_key == "refund.window.day_31",
        )
    )
    assert current_rule is not None and current_test is not None
    current_rule.condition = {
        "kind": "predicate",
        "fact": "state.days_since_delivery",
        "op": "gt",
        "value": 9999,
    }
    mutated = deepcopy(current_test.spec)
    mutated["scripted_trajectories"] = {arm: [] for arm in before.requested_arms}
    current_test.spec = mutated
    current_test.title = "MUTABLE ROW TITLE MUST NOT LEAK"
    await session.commit()

    after = await run_comparison(session, project.id, build.id)
    assert after.id != before.id
    assert after.metrics == before.metrics
    snapshots = list(
        (
            await session.scalars(
                select(ScenarioResult).where(ScenarioResult.run_id == after.id)
            )
        ).all()
    )
    day_31 = [
        result
        for result in snapshots
        if result.test_snapshot["stable_key"] == "refund.window.day_31"
    ]
    assert len(day_31) == 3
    assert {result.test_snapshot["title"] for result in day_31} == {
        "Refund on day 31 is rejected"
    }


@pytest.mark.parametrize(
    ("tool_name", "arguments", "error_code"),
    [
        ("invented_tool", {}, "unknown_tool"),
        ("get_order", {}, "missing_required_arguments"),
        ("get_order", "not-an-object", "malformed_tool_arguments"),
        ("get_order", {"order_id": 1042}, "invalid_tool_argument_type"),
        (
            "get_order",
            {"order_id": "N-1042", "debug": True},
            "unexpected_tool_arguments",
        ),
        (
            "issue_refund",
            {
                "order_id": "N-1042",
                "item_id": "I-88",
                "amount": 200.01,
                "destination": "original_payment",
            },
            "invalid_tool_argument_type",
        ),
        (
            "issue_refund",
            {
                "order_id": "N-1042",
                "item_id": "I-88",
                "amount": {
                    "currency": "USD",
                    "minor_units": 20001,
                    "decimal": 200.01,
                },
                "destination": "original_payment",
            },
            "unexpected_tool_arguments",
        ),
    ],
)
def test_invalid_tool_is_recorded_and_never_executes(
    tool_name: str, arguments: object, error_code: str
) -> None:
    initial_state = {"mutations": []}
    spec = {
        "initial_state": initial_state,
        "messages": [{"role": "user", "content": "Use an unknown tool"}],
        "events": [],
        "expected": {
            "guarded_decision": "allow",
            "forbidden_executed_tools": [],
            "assertions": [],
        },
        "scripted_trajectories": {
            "compiled_enforced": [
                {"type": "tool_call", "name": tool_name, "arguments": arguments}
            ]
        },
    }
    registry = json.loads((DEMO_DIR / "tools.json").read_text(encoding="utf-8"))
    events, final_state, metrics, _ = run_scenario(
        spec,
        "compiled_enforced",
        [],
        registry,
        {"artifacts": {}, "manifest": {}},
    )
    assert final_state == initial_state
    assert metrics["task_success"] is False
    assert metrics["tool_validation_errors"] == 1
    assert any(
        event["type"] == "error" and event["payload"]["code"] == error_code
        for event in events
    )
    assert not any(
        event["type"] in {"policy_evaluated", "tool_executed", "state_changed"}
        for event in events
    )


def test_northstar_tool_registry_pins_strict_draft_2020_12_schemas() -> None:
    registry = json.loads((DEMO_DIR / "tools.json").read_text(encoding="utf-8"))
    assert registry["schema_version"] == "0.2"
    assert registry["schema_dialect"] == DRAFT_2020_12_URI
    assert registry["tools"]
    for tool in registry["tools"]:
        schema = tool["input_schema"]
        assert schema["$schema"] == DRAFT_2020_12_URI
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False


def test_northstar_money_fixtures_use_exact_minor_units() -> None:
    facts = json.loads((DEMO_DIR / "orders.json").read_text(encoding="utf-8"))
    amounts: list[object] = [order["amount"] for order in facts["orders"]]
    for spec in northstar_test_specs():
        for trajectory in spec["scripted_trajectories"].values():
            for step in trajectory:
                arguments = step.get("arguments", {})
                if "amount" in arguments:
                    amounts.append(arguments["amount"])
        for event in spec["events"]:
            if "amount" in event.get("payload", {}):
                amounts.append(event["payload"]["amount"])
    assert amounts
    for amount in amounts:
        assert isinstance(amount, dict)
        assert set(amount) == {"currency", "minor_units"}
        assert amount["currency"] == "USD"
        assert isinstance(amount["minor_units"], int)
        assert not isinstance(amount["minor_units"], bool)


@pytest.mark.asyncio
async def test_seeded_refund_policy_compares_minor_units(
    session: AsyncSession,
) -> None:
    project = await seed_demo(session)
    rules = list(
        (
            await session.scalars(
                select(Rule).where(
                    Rule.project_id == project.id,
                    Rule.stable_key.in_(
                        [
                            "rule.refund.approval_threshold",
                            "rule.legacy.auto_250",
                        ]
                    ),
                )
            )
        ).all()
    )
    by_key = {rule.stable_key: rule for rule in rules}
    threshold = by_key["rule.refund.approval_threshold"].condition["conditions"][1]
    assert threshold == {
        "kind": "predicate",
        "fact": "tool.arguments.amount.minor_units",
        "op": "gt",
        "value": 20000,
    }
    assert by_key["rule.legacy.auto_250"].condition == {
        "kind": "predicate",
        "fact": "tool.arguments.amount.minor_units",
        "op": "lte",
        "value": 25000,
    }


def test_empty_trajectory_cannot_pass_vacuously() -> None:
    spec = {
        "initial_state": {},
        "messages": [{"role": "user", "content": "No assertion"}],
        "events": [],
        "expected": {
            "guarded_decision": "allow",
            "forbidden_executed_tools": [],
            "assertions": [],
        },
        "scripted_trajectories": {"compiled_enforced": []},
    }
    events, _, metrics, _ = run_scenario(
        spec,
        "compiled_enforced",
        [],
        {
            "schema_version": "0.2",
            "schema_dialect": DRAFT_2020_12_URI,
            "tools": [],
        },
        {"artifacts": {}, "manifest": {}},
    )
    assert metrics["task_success"] is False
    assert metrics["assertions"] == [
        {
            "kind": "explicit_assertion_required",
            "passed": False,
            "reason": "scenario_has_no_executable_or_compiler_assertion",
        }
    ]
    assert any(
        event["type"] == "error" and event["payload"]["code"] == "vacuous_scenario"
        for event in events
    )


@pytest.mark.asyncio
async def test_report_digest_and_exact_provenance_verify(
    session: AsyncSession,
) -> None:
    project = await seed_demo(session)
    await _make_buildable(session, project.id)
    build = await compile_project(session, project.id)
    run = await run_comparison(session, project.id, build.id)
    report = await create_report(session, run.id)

    assert run.metrics["coverage"]["compiler_assertion_case_count"] == 4
    assert run.metrics["coverage"]["compiler_assertion_coverage"] == 1
    assert run.metrics["coverage"]["explicit_assertion_coverage"] == 1
    payload = dict(report.evidence)
    digest = payload.pop("report_digest")
    assert bytes_hash(canonical_json_bytes(payload)) == digest
    assert report.content_hash == digest
    assert report.verdict == "Fixture suite passed"
    assert report.evidence["hashes"]["build_root_sha256"] == build.content_hash
    assert report.evidence["hashes"]["run_sha256"]
    assert report.evidence["hashes"]["test_suite_sha256"]
    assert report.evidence["hashes"]["tool_registry_sha256"]
    assert report.evidence["hashes"]["fact_fixture_sha256"]
    assert report.evidence["hashes"]["source_documents"]
    assert report.evidence["digest_definition"].startswith(
        "SHA-256 over canonical UTF-8 JSON bytes"
    )
