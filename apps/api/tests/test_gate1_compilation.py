import asyncio
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.routes import inspect_build
from app.auth import LOCAL_USER_EMAIL, LOCAL_USER_ID, AuthIdentity
from app.models import (
    Build,
    Document,
    Finding,
    GeneratedSpan,
    PlacementDecision,
    Project,
    Rule,
    Run,
)
from app.models import (
    TestCase as CaseModel,
)
from app.services.appointment_seed import PACK_DIR, seed_appointment_demo
from app.services.canonical import (
    artifact_bytes,
    artifact_hash,
    bytes_hash,
    canonical_json_bytes,
    canonical_json_text,
)
from app.services.compilation.provenance import protected_literals
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.reporting import create_report
from app.services.review import resolve_finding, revise_rule
from app.services.runner import run_comparison
from app.services.seed import seed_demo

REQUIRED_GATE1_ARTIFACTS = {
    "README.md",
    "compilation-metrics.json",
    "inputs/compiler-profile.json",
    "inputs/findings.json",
    "inputs/clause-inventory.json",
    "inputs/pinned-source-metadata.json",
    "inputs/placement-decisions.json",
    "inputs/rules.json",
    "manifest.json",
    "pending/unsupported-rules.json",
    "policies/tool-policy.json",
    "preservation-report.json",
    "prompt-kernel.md",
    "routing-report.json",
    "source-map.json",
    "tests/regression.yaml",
}


async def _project(session: AsyncSession, slug: str) -> Project:
    project = await session.scalar(select(Project).where(Project.slug == slug))
    assert project is not None
    return project


async def _resolve_critical_authority_conflicts(session: AsyncSession, project: Project) -> None:
    findings = list(
        (
            await session.scalars(
                select(Finding).where(
                    Finding.project_id == project.id,
                    Finding.severity == "critical",
                    Finding.resolution_state == "open",
                )
            )
        ).all()
    )
    for finding in findings:
        related = list(
            (await session.scalars(select(Rule).where(Rule.id.in_(finding.related_rule_ids)))).all()
        )
        winner = next(rule for rule in related if ".legacy" not in rule.stable_key)
        loser = next(rule for rule in related if ".legacy" in rule.stable_key)
        await resolve_finding(
            session,
            finding.id,
            "resolved",
            "The reviewed current authority supersedes the retained legacy source.",
            winner_rule_id=winner.id,
            loser_rule_id=loser.id,
            authority="Current authority metadata",
            actor="gate1-acceptance-test",
        )


async def _prepare_northstar(session: AsyncSession) -> Project:
    project = await _project(session, "northstar-retail")
    await _resolve_critical_authority_conflicts(session, project)
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
        changes={"reviewer_note": "The strict greater-than boundary is reviewed."},
        status="approved",
    )
    return project


async def _prepare_acme(session: AsyncSession) -> Project:
    project = await seed_appointment_demo(session)
    await _resolve_critical_authority_conflicts(session, project)
    return project


def _compile_acme_in_fresh_process(
    database_path: str,
) -> tuple[str, dict[str, bytes]]:
    async def run() -> tuple[str, dict[str, bytes]]:
        from app.db import Base

        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as child_session:
                project = await _prepare_acme(child_session)
                build = await compile_project(child_session, project.id)
                return build.content_hash, {
                    path: artifact_bytes(value) for path, value in sorted(build.artifacts.items())
                }
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _compile_northstar_in_fresh_process(
    database_path: str,
) -> tuple[str, dict[str, bytes]]:
    async def run() -> tuple[str, dict[str, bytes]]:
        from app.db import Base

        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as child_session:
                await seed_demo(child_session)
                project = await _prepare_northstar(child_session)
                build = await compile_project(child_session, project.id)
                return build.content_hash, {
                    path: artifact_bytes(value) for path, value in sorted(build.artifacts.items())
                }
        finally:
            await engine.dispose()

    return asyncio.run(run())


async def _assert_exact_source_map(
    session: AsyncSession, project: Project, build_artifacts: dict[str, str], source_map: dict
) -> None:
    documents = {
        (document.name, document.version): document
        for document in (
            await session.scalars(select(Document).where(Document.project_id == project.id))
        ).all()
    }
    assert source_map["range_convention"] == (
        "1-based inclusive lines; 0-based half-open UTF-8 byte ranges"
    )
    assert source_map["spans"]
    for span in source_map["spans"]:
        artifact_bytes = build_artifacts[span["artifact_path"]].encode("utf-8")
        assert bytes_hash(artifact_bytes) == span["artifact_sha256"]
        generated_bytes = artifact_bytes[span["utf8_byte_start"] : span["utf8_byte_end"]]
        assert bytes_hash(generated_bytes) == span["text_sha256"]
        generated_bytes.decode("utf-8")
        if span["transform_kind"] == "compiler_scaffold":
            assert span["source_refs"] == []
            continue
        assert span["rule_id"]
        assert span["placement_decision_id"]
        assert span["source_refs"]
        for anchor in span["source_refs"]:
            document = documents[(anchor["document_name"], anchor["document_version"])]
            source_bytes = document.normalized_text.encode("utf-8")
            quoted_bytes = source_bytes[anchor["utf8_byte_start"] : anchor["utf8_byte_end"]]
            assert quoted_bytes.decode("utf-8") == anchor["quote"]
            assert bytes_hash(quoted_bytes) == anchor["quote_sha256"]
            assert anchor["original_sha256"] == document.original_sha256
            assert anchor["normalized_sha256"] == document.normalized_sha256


@pytest.mark.asyncio
async def test_same_compiler_builds_two_domains_with_exact_gate1_evidence(
    session: AsyncSession,
) -> None:
    northstar = await _prepare_northstar(session)
    acme = await _prepare_acme(session)

    northstar_build = await compile_project(session, northstar.id)
    acme_build = await compile_project(session, acme.id)
    acme_inspection = await inspect_build(
        acme_build.id,
        identity=AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {}),
        session=session,
    )

    assert northstar_build.compiler_version == acme_build.compiler_version == "1.1.0"
    assert {
        key: northstar.compiler_profile[key] for key in ("name", "version", "path", "sha256")
    } == {key: acme.compiler_profile[key] for key in ("name", "version", "path", "sha256")}
    assert northstar.compiler_profile["agent_name"] != acme.compiler_profile["agent_name"]
    assert any(
        span.rule_stable_key == "rule.appointment.identity"
        and span.rule_revision == 1
        and span.placement_version == 1
        for span in acme_inspection.generated_spans
    )
    for project, build in ((northstar, northstar_build), (acme, acme_build)):
        assert REQUIRED_GATE1_ARTIFACTS <= set(build.artifacts)
        assert any(path.startswith("skills/") for path in build.artifacts)
        assert any(path.startswith("knowledge/") for path in build.artifacts)
        routing = json.loads(build.artifacts["routing-report.json"])
        inventory = json.loads(build.artifacts["inputs/clause-inventory.json"])
        metrics = json.loads(build.artifacts["compilation-metrics.json"])
        preservation = json.loads(build.artifacts["preservation-report.json"])
        assert json.loads(build.artifacts["source-map.json"]) == build.source_map
        placement_keys = {entry["placement"]["placement_key"] for entry in routing["entries"]}
        rule_keys = {entry["rule_key"] for entry in routing["entries"]}
        for span in build.source_map["spans"]:
            if span["placement_decision_id"] is not None:
                assert span["placement_decision_id"] in placement_keys
            if span["rule_id"] is not None:
                assert span["rule_id"] in rule_keys
        assert routing["counts"]["active"] == len(routing["entries"])
        assert routing["counts"]["active"] == sum(
            routing["counts"][name] for name in ("routed", "blocked", "unsupported", "retired")
        )
        declared = {
            (source["document"], source["version"], line)
            for source in inventory["sources"]
            for line in source["lines"]
        }
        coverage: dict[tuple[str, int, int], list[str]] = {}
        for entry in routing["entries"]:
            for anchor in entry["source_anchors"]:
                for line in range(anchor["line_start"], anchor["line_end"] + 1):
                    coverage.setdefault(
                        (anchor["document_name"], anchor["document_version"], line), []
                    ).append(entry["rule_key"])
        assert set(coverage) == declared
        assert all(len(rule_keys) == 1 for rule_keys in coverage.values())
        assert metrics["routing"]["routing_coverage"] == 1
        assert metrics["routing"]["unrouted_count"] == 0
        assert metrics["behavioral_fidelity"] == "not_measured"
        assert preservation["behavioral_fidelity"] == "not_measured"
        assert "lossless" not in preservation["interpretation"].lower()
        await _assert_exact_source_map(session, project, build.artifacts, build.source_map)
        persisted_span_count = await session.scalar(
            select(func.count())
            .select_from(GeneratedSpan)
            .where(GeneratedSpan.build_id == build.id)
        )
        assert persisted_span_count == len(build.source_map["spans"])

    acme_routing = json.loads(acme_build.artifacts["routing-report.json"])
    acme_sources = json.loads(acme_build.artifacts["inputs/pinned-source-metadata.json"])["sources"]
    current_policy = next(item for item in acme_sources if item["name"] == "booking-policy-v2.md")
    assert current_policy["authority"]["supersedes_document_key"] == ("booking-sop-legacy.md@1")
    unsupported = json.loads(acme_build.artifacts["pending/unsupported-rules.json"])
    unsupported_dispositions = {
        entry["rule_stable_key"]
        for entry in acme_routing["entries"]
        if entry["disposition"] == "unsupported"
    }
    assert "rule.appointment.daylight" in unsupported_dispositions
    unsupported_skill_lines = {
        anchor["line_start"]
        for entry in acme_routing["entries"]
        if entry["disposition"] == "unsupported"
        for anchor in entry["source_anchors"]
        if anchor["document_name"] == "SKILL.md"
    }
    assert set(range(411, 419)) <= unsupported_skill_lines
    assert {entry["rule_stable_key"] for entry in unsupported["rules"]} >= {
        "rule.appointment.daylight",
        "rule.appointment.reschedule_limit",
        "rule.appointment.cooldown",
    }
    skill_rules = [
        entry
        for entry in acme_routing["entries"]
        if entry["source_anchors"]
        and entry["source_anchors"][0]["document_name"] == "SKILL.md"
        and entry["source_anchors"][0]["quote"].startswith("ACME-")
    ]
    assert len(skill_rules) == 382
    assert acme_routing["counts"]["retired"] >= 10
    assert all(entry["placement"]["reviewer"] == "Aletheia fixture author" for entry in skill_rules)
    assert all(entry["rationale"] for entry in skill_rules)
    preservation = json.loads(acme_build.artifacts["preservation-report.json"])
    literal_kinds = {
        literal["kind"] for check in preservation["checks"] for literal in check["literals"]
    }
    assert {"tool_name", "enum_value", "structured_literal"} <= literal_kinds
    assert all(check["preserved"] for check in preservation["checks"]), [
        check for check in preservation["checks"] if not check["preserved"]
    ]
    assert len((PACK_DIR / "SKILL.md").read_text(encoding="utf-8").splitlines()) >= 400


def test_acme_build_is_byte_identical_across_fresh_processes(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
        futures = [
            pool.submit(
                _compile_acme_in_fresh_process,
                str(tmp_path / f"acme-process-{index}.db"),
            )
            for index in range(2)
        ]
        first, second = [future.result(timeout=90) for future in futures]

    assert first == second
    assert bytes_hash(first[1]["manifest.json"]) == first[0]


def test_northstar_build_is_byte_identical_across_fresh_processes(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=context) as pool:
        futures = [
            pool.submit(
                _compile_northstar_in_fresh_process,
                str(tmp_path / f"northstar-process-{index}.db"),
            )
            for index in range(2)
        ]
        first, second = [future.result(timeout=90) for future in futures]

    assert first == second
    assert bytes_hash(first[1]["manifest.json"]) == first[0]


@pytest.mark.asyncio
async def test_acme_uses_the_shared_runner_and_never_executes_guarded_mutations(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    build = await compile_project(session, project.id)
    run = await run_comparison(session, project.id, build.id)

    assert run.metrics["coverage"]["test_count"] == 10
    assert run.metrics["compiled_enforced"]["executed_violation_rate"] == 0
    assert run.metrics["coverage"]["declared_rule_linkage"]["ratio"] == 1
    assert run.metrics["coverage"]["declared_source_linkage"]["ratio"] == 1
    assert run.dataset_manifest["data_scope"] == "evaluation"


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["missing", "quote", "hash"])
async def test_approved_source_provenance_fails_closed(session: AsyncSession, tamper: str) -> None:
    project = await _prepare_acme(session)
    rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.identity",
        )
    )
    assert rule is not None
    source_refs = [dict(item) for item in rule.source_refs]
    if tamper == "missing":
        source_refs = []
        expected_code = "approved_rule_provenance_missing"
    elif tamper == "quote":
        source_refs[0]["quote"] += " forged"
        expected_code = "source_anchor_quote_mismatch"
    else:
        source_refs[0]["source_sha256"] = "0" * 64
        expected_code = "source_anchor_hash_mismatch"
    rule.source_refs = source_refs
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == expected_code


@pytest.mark.asyncio
async def test_unknown_placement_destination_fails_closed(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.style",
        )
    )
    assert rule is not None
    placement = await session.scalar(
        select(PlacementDecision).where(PlacementDecision.rule_id == rule.id)
    )
    assert placement is not None
    placement.destinations = ["unknown_destination"]
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "placement_destination_unknown"


@pytest.mark.asyncio
async def test_unknown_rule_category_fails_closed(session: AsyncSession) -> None:
    project = await _prepare_acme(session)
    rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.style",
        )
    )
    assert rule is not None
    rule.category = "fixture_unknown"
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "rule_classification_unknown"


@pytest.mark.asyncio
async def test_incompatible_agent_profile_fails_closed(session: AsyncSession) -> None:
    project = await _prepare_acme(session)
    profile = deepcopy(project.compiler_profile)
    profile["agent_name"] = "A different agent contract"
    project.compiler_profile = profile
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "compiler_profile_scope_mismatch"


@pytest.mark.asyncio
async def test_clause_inventory_pin_change_fails_closed(session: AsyncSession) -> None:
    project = await _prepare_acme(session)
    config = deepcopy(project.compilation_config)
    config["clause_inventory"]["sha256"] = "0" * 64
    project.compilation_config = config
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "clause_inventory_digest_mismatch"


@pytest.mark.asyncio
async def test_unknown_compiler_profile_fails_closed(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    project.compiler_profile = {
        "name": "unknown-profile",
        "version": "1.0.0",
        "path": "compiler-profiles/not-installed.json",
    }
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "compiler_profile_unknown"


@pytest.mark.asyncio
async def test_superseded_authority_cannot_be_routed(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    style = await session.scalar(
        select(Document).where(
            Document.project_id == project.id,
            Document.name == "appointment-style.md",
        )
    )
    assert style is not None
    style.authority_status = "superseded"
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "stale_authority_routed"


@pytest.mark.asyncio
async def test_high_severity_rule_requires_guard_and_test_placement(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.hours",
        )
    )
    assert rule is not None
    placement = await session.scalar(
        select(PlacementDecision).where(PlacementDecision.rule_id == rule.id)
    )
    assert placement is not None
    placement.destinations = ["skill", "test"]
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "critical_placement_incomplete"


@pytest.mark.asyncio
async def test_new_reviewed_placement_version_changes_the_build_root(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    first = await compile_project(session, project.id)
    rule = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.style",
        )
    )
    assert rule is not None
    current = await session.scalar(
        select(PlacementDecision)
        .where(PlacementDecision.rule_id == rule.id)
        .order_by(PlacementDecision.version.desc())
    )
    assert current is not None
    session.add(
        PlacementDecision(
            project_id=project.id,
            rule_id=rule.id,
            version=current.version + 1,
            profile_name=current.profile_name,
            profile_version=current.profile_version,
            destinations=current.destinations,
            scope_slug=current.scope_slug,
            rendering=current.rendering,
            transform_kind=current.transform_kind,
            disposition=current.disposition,
            rationale="Re-reviewed for the Gate 1 acceptance snapshot.",
            review_status="approved",
            reviewer="Gate 1 acceptance reviewer",
        )
    )
    await session.commit()

    second = await compile_project(session, project.id)
    assert second.id != first.id
    assert second.input_hash != first.input_hash
    assert second.content_hash != first.content_hash
    placements = json.loads(second.artifacts["inputs/placement-decisions.json"])
    style = next(
        item
        for item in placements["placements"]
        if item["rule_stable_key"] == "rule.appointment.style"
    )
    assert style["version"] == 2
    assert style["reviewer"] == "Gate 1 acceptance reviewer"


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_input", ["source", "rule", "test", "profile"])
async def test_every_semantic_input_digest_invalidates_without_mutating_old_build(
    session: AsyncSession, changed_input: str
) -> None:
    project = await _prepare_acme(session)
    first = await compile_project(session, project.id)
    first_snapshot = {
        "input_hash": first.input_hash,
        "content_hash": first.content_hash,
        "artifacts": deepcopy(first.artifacts),
        "source_map": deepcopy(first.source_map),
        "stats": deepcopy(first.stats),
    }
    if changed_input == "source":
        source = await session.scalar(
            select(Document).where(
                Document.project_id == project.id,
                Document.name == "evaluation-data.json",
            )
        )
        assert source is not None
        # Whitespace is a semantic source-snapshot change, remains valid JSON,
        # and does not invalidate any source-anchored clause provenance.
        source.normalized_text += "\n"
        source.normalized_sha256 = bytes_hash(source.normalized_text.encode("utf-8"))
        source.original_sha256 = source.normalized_sha256
        source.line_count = len(source.normalized_text.splitlines())
    elif changed_input == "rule":
        rule = await session.scalar(
            select(Rule).where(
                Rule.project_id == project.id,
                Rule.stable_key == "rule.appointment.style",
            )
        )
        assert rule is not None
        rule.reviewer_note = "Re-reviewed semantic rule input."
    elif changed_input == "test":
        test = await session.scalar(
            select(CaseModel).where(
                CaseModel.project_id == project.id,
                CaseModel.stable_key == "appointment.style.timezone",
            )
        )
        assert test is not None
        spec = deepcopy(test.spec)
        spec["title"] = f"{spec['title']} (reviewed)"
        test.spec = spec
    else:
        profile = deepcopy(project.compiler_profile)
        profile["response_contract"] += " Return the reviewed fixture marker."
        project.compiler_profile = profile
    await session.commit()

    second = await compile_project(session, project.id)
    assert second.id != first.id
    assert second.input_hash != first_snapshot["input_hash"]
    assert second.content_hash != first_snapshot["content_hash"]
    persisted_first = await session.get(Build, first.id)
    assert persisted_first is not None
    assert persisted_first.artifacts == first_snapshot["artifacts"]
    assert persisted_first.source_map == first_snapshot["source_map"]
    assert persisted_first.stats == first_snapshot["stats"]


@pytest.mark.asyncio
async def test_pre_1_1_gate1_build_remains_inspectable_runnable_and_reportable(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    current = await compile_project(session, project.id)
    artifacts = deepcopy(current.artifacts)
    routing = json.loads(artifacts["routing-report.json"])
    routing["entries"] = [
        entry for entry in routing["entries"] if entry["disposition"] != "retired"
    ]
    for entry in routing["entries"]:
        entry.pop("decidability", None)
    routing["counts"] = {
        "active": len(routing["entries"]),
        "routed": sum(entry["disposition"] == "routed" for entry in routing["entries"]),
        "blocked": sum(entry["disposition"] == "blocked" for entry in routing["entries"]),
        "unsupported": sum(
            entry["disposition"] == "unsupported" for entry in routing["entries"]
        ),
    }
    artifacts["routing-report.json"] = canonical_json_text(routing)
    metrics = deepcopy(current.stats["compilation"])
    metrics["routing"].pop("retired_count")
    artifacts["compilation-metrics.json"] = canonical_json_text(metrics)
    stats = deepcopy(current.stats)
    stats["compilation"] = metrics

    inputs = deepcopy(current.input_manifest)
    inputs["compiler"]["version"] = "1.0.0"
    inputs["compiler_profile"].pop("project_digest")
    input_hash = bytes_hash(canonical_json_bytes(inputs))
    manifest = json.loads(artifacts["manifest.json"])
    manifest["compiler_version"] = "1.0.0"
    manifest["inputs"] = inputs
    manifest["input_hash"] = input_hash
    manifest["artifact_hashes"] = {
        path: artifact_hash(value)
        for path, value in sorted(artifacts.items())
        if path != "manifest.json"
    }
    manifest_text = canonical_json_text(manifest)
    content_hash = bytes_hash(manifest_text.encode("utf-8"))
    artifacts["manifest.json"] = manifest_text
    legacy = Build(
        project_id=project.id,
        status="succeeded",
        input_manifest=inputs,
        input_hash=input_hash,
        compiler_version="1.0.0",
        artifacts=artifacts,
        source_map=current.source_map,
        stats=stats,
        content_hash=content_hash,
    )
    session.add(legacy)
    await session.commit()

    inspection = await inspect_build(
        legacy.id,
        identity=AuthIdentity(LOCAL_USER_ID, LOCAL_USER_EMAIL, {}),
        session=session,
    )
    assert inspection.routing_report is not None
    assert inspection.routing_report.counts.retired == 0
    assert inspection.stats is not None
    assert inspection.stats.compilation.routing.retired_count == 0
    run = await run_comparison(session, project.id, legacy.id)
    report = await create_report(session, run.id)
    assert run.status == "succeeded"
    assert report.content_hash


@pytest.mark.asyncio
async def test_acme_reset_is_repeatable_tenant_scoped_and_preserves_project_ids(
    session: AsyncSession,
) -> None:
    northstar = await _project(session, "northstar-retail")
    northstar_rule_count = await session.scalar(
        select(func.count()).select_from(Rule).where(Rule.project_id == northstar.id)
    )
    acme = await _prepare_acme(session)
    acme_id = acme.id
    build = await compile_project(session, acme.id)
    await run_comparison(session, acme.id, build.id)

    first_reset = await seed_appointment_demo(session, workspace_id=acme.workspace_id, reset=True)
    second_reset = await seed_appointment_demo(session, workspace_id=acme.workspace_id, reset=True)
    assert first_reset.id == second_reset.id == acme_id
    assert (
        await session.scalar(
            select(func.count()).select_from(Build).where(Build.project_id == acme_id)
        )
        == 0
    )
    assert (
        await session.scalar(select(func.count()).select_from(Run).where(Run.project_id == acme_id))
        == 0
    )
    acme_rules = list((await session.scalars(select(Rule).where(Rule.project_id == acme_id))).all())
    inventory = json.loads((PACK_DIR / "clause-inventory.json").read_text(encoding="utf-8"))
    inventory_count = sum(len(source["lines"]) for source in inventory["sources"])
    assert len(acme_rules) == inventory_count
    assert len({rule.stable_key for rule in acme_rules}) == inventory_count
    assert (
        await session.scalar(
            select(func.count()).select_from(Rule).where(Rule.project_id == northstar.id)
        )
        == northstar_rule_count
    )


@pytest.mark.asyncio
async def test_reviewer_authored_guidance_has_explicit_auditable_provenance(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    template = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.style",
        )
    )
    assert template is not None
    template_placement = await session.scalar(
        select(PlacementDecision).where(PlacementDecision.rule_id == template.id)
    )
    assert template_placement is not None
    rule = Rule(
        project_id=project.id,
        stable_key="rule.appointment.reviewer_guidance",
        revision=1,
        title="Reviewed scheduling guidance",
        normative_text="Acknowledge the customer's requested time before proposing alternatives.",
        category=template.category,
        effect=template.effect,
        severity="low",
        status="approved",
        confidence=1.0,
        scope=deepcopy(template.scope),
        condition=deepcopy(template.condition),
        requires=deepcopy(template.requires),
        enforcement=template.enforcement,
        decidability=template.decidability,
        source_refs=[],
        target_tools=deepcopy(template.target_tools),
        exceptions=deepcopy(template.exceptions),
        reviewer_note="Approved during policy reconciliation.",
        provenance_kind="reviewer_authored_guidance",
        provenance_metadata={
            "reviewer": "Scheduling policy council",
            "rationale": "Reviewed customer-facing guidance authored during reconciliation.",
            "reviewed_at": "2026-08-04T15:30:00Z",
        },
    )
    session.add(rule)
    await session.flush()
    session.add(
        PlacementDecision(
            project_id=project.id,
            rule_id=rule.id,
            version=1,
            profile_name=template_placement.profile_name,
            profile_version=template_placement.profile_version,
            destinations=["prompt_kernel"],
            scope_slug=template_placement.scope_slug,
            rendering=rule.normative_text,
            transform_kind="reviewer_authored_guidance",
            disposition="routed",
            rationale="Reviewed customer-facing guidance authored during reconciliation.",
            review_status="approved",
            reviewer="Scheduling policy council",
        )
    )
    await session.commit()

    build = await compile_project(session, project.id)
    routing = json.loads(build.artifacts["routing-report.json"])
    entry = next(item for item in routing["entries"] if item["rule_stable_key"] == rule.stable_key)
    assert entry["provenance_kind"] == "reviewer_authored_guidance"
    assert entry["provenance_metadata"]["reviewer"] == ("Scheduling policy council")
    assert entry["verified_source_anchors"] == 0
    rule_spans = [
        span for span in build.source_map["spans"] if span["rule_stable_key"] == rule.stable_key
    ]
    # Rule-derived spans keep the reviewed provenance kind. Compiler-authored
    # headings are represented separately and must never masquerade as a rule.
    assert {span["transform_kind"] for span in rule_spans} == {
        "reviewer_authored_guidance"
    }
    assert any(
        span["transform_kind"] == "compiler_scaffold"
        and span["rule_stable_key"] is None
        for span in build.source_map["spans"]
    )
    assert (
        next(span for span in rule_spans if span["transform_kind"] == "reviewer_authored_guidance")[
            "source_refs"
        ]
        == []
    )


@pytest.mark.asyncio
async def test_reviewer_guidance_without_review_timestamp_fails_closed(
    session: AsyncSession,
) -> None:
    project = await _prepare_acme(session)
    template = await session.scalar(
        select(Rule).where(
            Rule.project_id == project.id,
            Rule.stable_key == "rule.appointment.style",
        )
    )
    assert template is not None
    template_placement = await session.scalar(
        select(PlacementDecision).where(PlacementDecision.rule_id == template.id)
    )
    assert template_placement is not None
    rule = Rule(
        project_id=project.id,
        stable_key="rule.appointment.incomplete_reviewer_guidance",
        revision=1,
        title="Incomplete reviewed scheduling guidance",
        normative_text="Acknowledge the customer's requested time.",
        category=template.category,
        effect=template.effect,
        severity="low",
        status="approved",
        confidence=1.0,
        scope=deepcopy(template.scope),
        condition=deepcopy(template.condition),
        requires=deepcopy(template.requires),
        enforcement=template.enforcement,
        decidability=template.decidability,
        source_refs=[],
        target_tools=deepcopy(template.target_tools),
        exceptions=deepcopy(template.exceptions),
        reviewer_note="Missing timestamp must fail closed.",
        provenance_kind="reviewer_authored_guidance",
        provenance_metadata={
            "reviewer": "Scheduling policy council",
            "rationale": "A rationale without its review time is incomplete.",
        },
    )
    session.add(rule)
    await session.flush()
    session.add(
        PlacementDecision(
            project_id=project.id,
            rule_id=rule.id,
            version=1,
            profile_name=template_placement.profile_name,
            profile_version=template_placement.profile_version,
            destinations=["prompt_kernel"],
            scope_slug=template_placement.scope_slug,
            rendering=rule.normative_text,
            transform_kind="reviewer_authored_guidance",
            disposition="routed",
            rationale="A rationale without its review time is incomplete.",
            review_status="approved",
            reviewer="Scheduling policy council",
        )
    )
    await session.commit()

    with pytest.raises(ServiceError) as captured:
        await compile_project(session, project.id)
    assert captured.value.code == "reviewer_guidance_provenance_missing"


def test_generic_compiler_core_contains_no_fixture_semantics() -> None:
    app_root = Path(__file__).parents[1] / "app"
    service_root = app_root / "services"
    paths = [
        service_root / "compiler.py",
        *(service_root / "compilation").glob("*.py"),
        app_root / "api" / "routes.py",
    ]
    forbidden = ("northstar", "refund", "appointment", "issue_refund", "acme")
    text = "\n".join(path.read_text(encoding="utf-8").casefold() for path in paths)
    assert all(term not in text for term in forbidden)


def test_protected_literal_extraction_does_not_invent_thresholds_from_ids() -> None:
    literals = protected_literals(
        "ACME-STYLE-001: Require approval above $200 after 30 days.",
        [],
    )
    thresholds = {item["value"] for item in literals if item["kind"] == "threshold_or_duration"}
    assert thresholds == {"$200", "30 days"}
