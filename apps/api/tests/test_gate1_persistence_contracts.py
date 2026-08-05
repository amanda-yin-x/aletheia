from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import LOCAL_USER_EMAIL, LOCAL_USER_ID
from app.db import Base, get_session
from app.main import app
from app.models import (
    Build,
    PlacementDecision,
    Project,
    Rule,
    UserAccount,
    Workspace,
    WorkspaceMembership,
)
from app.models import (
    GeneratedSpan as GeneratedSpanModel,
)
from app.schemas import (
    CompilationConfig,
    CompilerProfile,
    GeneratedSpan,
    ManifestPlacementInput,
    PlacementDecisionContract,
    PreservationReport,
    RuleProvenance,
    SourceAnchor,
    SourceMapArtifact,
)
from app.services.canonical import artifact_hash, bytes_hash, canonical_json_bytes

API_ROOT = Path(__file__).resolve().parents[1]


def _source_anchor(quote: str = "An exact reviewed sentence.") -> dict[str, Any]:
    quote_sha256 = bytes_hash(quote.encode("utf-8"))
    identity = {
        "document_name": "policy.md",
        "document_version": 3,
        "normalized_sha256": "b" * 64,
        "line_start": 4,
        "line_end": 4,
        "quote_sha256": quote_sha256,
    }
    return {
        "source_anchor_id": bytes_hash(canonical_json_bytes(identity)),
        "document_key": "policy.md@3",
        "document_name": "policy.md",
        "document_version": 3,
        "version_label": "Policy v3",
        "authority_owner": "Policy Operations",
        "authority_status": "current",
        "original_sha256": "a" * 64,
        "normalized_sha256": "b" * 64,
        "line_start": 4,
        "line_end": 4,
        "utf8_byte_start": 30,
        "utf8_byte_end": 30 + len(quote.encode("utf-8")),
        "quote": quote,
        "quote_sha256": quote_sha256,
        "parser": "checked_in_utf8",
        "parser_version": "1.0.0",
        "normalizer": "aletheia_text",
        "normalizer_version": "1.0.0",
    }


@pytest.fixture
def northstar_compilation_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "bundle_slug": "refund-operations",
        "agent_label": "Northstar Retail support agent",
        "skill_title": "Refund operations",
        "knowledge_title": "Retail policy reference",
        "suite_name": "Aletheia-authored refund boundary suite",
        "suite_version": 3,
        "inputs": {
            "baseline_prompt": {"name": "baseline-system-prompt.md", "version": 1},
            "tool_schema": {"name": "tools.json", "version": 1},
            "evaluation_data": {"name": "orders.json", "version": 1},
        },
        "expected_context": [
            "prompt-kernel.md",
            "skills/refund-operations/SKILL.md",
            "knowledge/refund-operations.md",
        ],
    }


def test_gate1_contracts_are_strict_and_byte_addressed(
    northstar_compilation_config: dict[str, Any],
) -> None:
    profile = CompilerProfile.model_validate(
        {
            "name": "source-aware",
            "version": "1.0.0",
            "path": "compiler-profiles/source-aware-v1.json",
        }
    )
    assert profile.version == "1.0.0"
    assert CompilationConfig.model_validate(northstar_compilation_config).suite_version == 3

    anchor = SourceAnchor.model_validate(_source_anchor())
    span = GeneratedSpan.model_validate(
        {
            "artifact_path": "prompt-kernel.md",
            "artifact_sha256": "c" * 64,
            "rule_id": "rule.refund.window@1",
            "rule_stable_key": "rule.refund.window",
            "rule_revision": 1,
            "placement_decision_id": "rule.refund.window@1:placement:2",
            "placement_version": 2,
            "line_start": 4,
            "line_end": 4,
            "utf8_byte_start": 30,
            "utf8_byte_end": 58,
            "transform_kind": "verbatim",
            "text_sha256": "d" * 64,
            "source_refs": [anchor.model_dump()],
        }
    )
    source_map = SourceMapArtifact.model_validate(
        {
            "schema_version": "1.0",
            "range_convention": (
                "1-based inclusive lines; 0-based half-open UTF-8 byte ranges"
            ),
            "spans": [span.model_dump()],
        }
    )
    assert source_map.spans[0].source_refs[0].quote == anchor.quote

    report = PreservationReport.model_validate(
        {
            "schema_version": "1.0",
            "checks": [
                {
                    "rule_key": "rule.refund.window@1",
                    "artifact_paths": ["prompt-kernel.md"],
                    "literals": [{"kind": "threshold_or_duration", "value": "30"}],
                    "missing": [],
                    "preserved": True,
                }
            ],
            "behavioral_fidelity": "not_measured",
            "interpretation": "Deterministic conformance only.",
        }
    )
    assert report.behavioral_fidelity == "not_measured"

    with pytest.raises(ValidationError, match="quote_sha256"):
        SourceAnchor.model_validate({**_source_anchor(), "quote_sha256": "0" * 64})
    with pytest.raises(ValidationError, match="source-derived spans"):
        GeneratedSpan.model_validate(
            {
                **span.model_dump(),
                "source_refs": [],
            }
        )
    with pytest.raises(ValidationError, match="reviewer-authored guidance"):
        RuleProvenance.model_validate(
            {"kind": "reviewer_authored_guidance", "metadata": {}}
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CompilerProfile.model_validate(
            {
                "name": "source-aware",
                "version": "1.0.0",
                "path": "profile.json",
                "unknown": True,
            }
        )


def test_placement_contract_and_manifest_digest_are_self_consistent() -> None:
    record = {
        "placement_key": "rule.example@2:placement:3",
        "rule_key": "rule.example@2",
        "rule_stable_key": "rule.example",
        "rule_revision": 2,
        "version": 3,
        "profile_name": "source-aware",
        "profile_version": "1.0.0",
        "destinations": ["skill", "test"],
        "scope_slug": "refund-operations",
        "rendering": "Use the reviewed rule.",
        "transform_kind": "reviewed_normalization",
        "disposition": "routed",
        "rationale": "Reviewed placement.",
        "review_status": "approved",
        "reviewer": "Reviewer",
    }
    digest = bytes_hash(canonical_json_bytes(record))
    assert ManifestPlacementInput.model_validate({**record, "digest": digest}).digest == digest
    with pytest.raises(ValidationError, match="placement digest"):
        ManifestPlacementInput.model_validate({**record, "digest": "0" * 64})
    with pytest.raises(ValidationError, match="destinations must be unique"):
        PlacementDecisionContract.model_validate(
            {
                "project_id": "project",
                "rule_id": "rule",
                "version": 1,
                "profile_name": "source-aware",
                "profile_version": "1.0.0",
                "destinations": ["test", "test"],
                "scope_slug": "refund-operations",
                "rendering": None,
                "transform_kind": "verbatim",
                "disposition": "routed",
                "rationale": "Reviewed placement.",
                "review_status": "approved",
                "reviewer": "Reviewer",
            }
        )


def test_exported_gate1_contracts_and_openapi_are_current() -> None:
    expected_contracts = {
        "BuildInspectionOut",
        "CompilationConfig",
        "CompilationMetrics",
        "CompilerProfile",
        "GeneratedSpan",
        "PlacementDecisionContract",
        "PreservationReport",
        "RoutingReport",
        "SourceAnchor",
        "SourceMapArtifact",
        "UnsupportedRulesArtifact",
    }
    for contract in expected_contracts:
        path = API_ROOT / "schemas" / f"{contract}.schema.json"
        assert path.is_file(), f"missing exported contract: {path.name}"
        schema = json.loads(path.read_text())
        assert schema["additionalProperties"] is False

    generated_span = json.loads(
        (API_ROOT / "schemas" / "GeneratedSpan.schema.json").read_text()
    )
    assert {
        "artifact_sha256",
        "artifact_path",
        "line_start",
        "line_end",
        "utf8_byte_start",
        "utf8_byte_end",
        "source_refs",
        "text_sha256",
        "transform_kind",
    } <= set(generated_span["properties"])

    evidence = json.loads(
        (API_ROOT / "schemas" / "EvidencePayload.schema.json").read_text()
    )
    coverage_properties = evidence["$defs"]["CoverageMetrics"]["properties"]
    assert {
        "declared_rule_linkage",
        "declared_source_linkage",
        "declared_boundary_linkage",
    } <= set(coverage_properties)
    assert not {
        "rule_coverage",
        "source_coverage",
        "boundary_coverage",
    } & set(coverage_properties)

    openapi = json.loads((API_ROOT / "openapi.json").read_text())
    assert "get" in openapi["paths"][
        "/api/v1/projects/{project_id}/placement-decisions"
    ]
    assert "patch" in openapi["paths"][
        "/api/v1/placement-decisions/{placement_decision_id}"
    ]
    assert "get" in openapi["paths"]["/api/v1/builds/{build_id}/inspection"]


@pytest_asyncio.fixture
async def gate1_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, dict[str, str]]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'gate1.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        account = UserAccount(
            id=LOCAL_USER_ID,
            email=LOCAL_USER_EMAIL,
            is_anonymous=False,
        )
        workspace = Workspace(
            id="workspace-local",
            slug="workspace-local",
            name="Local workspace",
            created_by_user_id=LOCAL_USER_ID,
        )
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=LOCAL_USER_ID,
            role="owner",
        )
        project = Project(
            id="project-local",
            workspace_id=workspace.id,
            slug="example-project",
            name="Example",
            domain="example",
            description="A typed Gate 1 fixture.",
            mode="demo",
        )
        rule = Rule(
            id="rule-local",
            project_id=project.id,
            stable_key="rule.example",
            revision=1,
            title="Example rule",
            normative_text="Use the reviewed rule.",
            category="workflow",
            effect="observe_only",
            severity="low",
            status="approved",
            confidence=1.0,
            scope={},
            condition={},
            requires=[],
            enforcement="prompt",
            decidability="human",
            source_refs=[],
            target_tools=[],
            exceptions=[],
            reviewer_note="",
        )
        placement = PlacementDecision(
            id="placement-local-v1",
            project_id=project.id,
            rule_id=rule.id,
            version=1,
            profile_name="source-aware",
            profile_version="1.0.0",
            destinations=["skill"],
            scope_slug="example-scope",
            rendering=rule.normative_text,
            transform_kind="verbatim",
            disposition="routed",
            rationale="Initial reviewed placement.",
            review_status="approved",
            reviewer="Reviewer",
        )
        artifact = "# Kernel\n"
        build = Build(
            id="build-local",
            project_id=project.id,
            status="succeeded",
            input_manifest={},
            input_hash="e" * 64,
            compiler_version="1.0.0",
            artifacts={"prompt-kernel.md": artifact},
            source_map={
                "schema_version": "1.0",
                "range_convention": (
                    "1-based inclusive lines; 0-based half-open UTF-8 byte ranges"
                ),
                "spans": [],
            },
            stats={"behavioral_fidelity": "not_measured"},
            content_hash="f" * 64,
        )
        generated_span = GeneratedSpanModel(
            id="span-local",
            build_id=build.id,
            artifact_path="prompt-kernel.md",
            artifact_sha256=artifact_hash(artifact),
            line_start=1,
            line_end=1,
            utf8_byte_start=0,
            utf8_byte_end=len(artifact.encode("utf-8")),
            transform_kind="compiler_scaffold",
            text_sha256=hashlib.sha256(artifact.encode("utf-8")).hexdigest(),
            source_refs=[],
        )

        other_account = UserAccount(
            id="user-other", email="other@example.test", is_anonymous=False
        )
        other_workspace = Workspace(
            id="workspace-other",
            slug="workspace-other",
            name="Other workspace",
            created_by_user_id=other_account.id,
        )
        other_membership = WorkspaceMembership(
            workspace_id=other_workspace.id,
            user_id=other_account.id,
            role="owner",
        )
        other_project = Project(
            id="project-other",
            workspace_id=other_workspace.id,
            slug="other-project",
            name="Other",
            domain="other",
            description="Other tenant.",
            mode="demo",
        )
        other_rule = Rule(
            id="rule-other",
            project_id=other_project.id,
            stable_key="rule.other",
            revision=1,
            title="Other rule",
            normative_text="Other tenant rule.",
            category="workflow",
            effect="observe_only",
            severity="low",
            status="approved",
            confidence=1.0,
            scope={},
            condition={},
            requires=[],
            enforcement="prompt",
            decidability="human",
            source_refs=[],
            target_tools=[],
            exceptions=[],
            reviewer_note="",
        )
        other_placement = PlacementDecision(
            id="placement-other-v1",
            project_id=other_project.id,
            rule_id=other_rule.id,
            version=1,
            profile_name="source-aware",
            profile_version="1.0.0",
            destinations=["skill"],
            scope_slug="other-scope",
            rendering=other_rule.normative_text,
            transform_kind="verbatim",
            disposition="routed",
            rationale="Other tenant placement.",
            review_status="approved",
            reviewer="Other reviewer",
        )
        session.add_all(
            [
                account,
                workspace,
                membership,
                project,
                rule,
                placement,
                build,
                generated_span,
                other_account,
                other_workspace,
                other_membership,
                other_project,
                other_rule,
                other_placement,
            ]
        )
        await session.commit()
        yield session, {
            "project_id": project.id,
            "placement_id": placement.id,
            "foreign_placement_id": other_placement.id,
            "build_id": build.id,
            "artifact_sha256": artifact_hash(artifact),
        }
    await engine.dispose()


@pytest.mark.asyncio
async def test_placement_api_is_tenant_scoped_append_only_and_optimistic(
    gate1_session: tuple[AsyncSession, dict[str, str]],
) -> None:
    session, ids = gate1_session

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            listed = await client.get(
                f"/api/v1/projects/{ids['project_id']}/placement-decisions"
            )
            assert listed.status_code == 200
            assert [item["version"] for item in listed.json()] == [1]

            revised = await client.patch(
                f"/api/v1/placement-decisions/{ids['placement_id']}",
                json={
                    "expected_version": 1,
                    "rationale": "Second reviewed placement.",
                },
            )
            assert revised.status_code == 200
            revised_payload = revised.json()
            assert revised_payload["id"] != ids["placement_id"]
            assert revised_payload["version"] == 2

            stale = await client.patch(
                f"/api/v1/placement-decisions/{ids['placement_id']}",
                json={"expected_version": 1, "rationale": "Stale overwrite."},
            )
            assert stale.status_code == 409

            foreign = await client.patch(
                f"/api/v1/placement-decisions/{ids['foreign_placement_id']}",
                json={"expected_version": 1, "rationale": "Cross-tenant write."},
            )
            assert foreign.status_code == 404
    finally:
        app.dependency_overrides.pop(get_session, None)

    history = list(
        (
            await session.scalars(
                select(PlacementDecision)
                .where(PlacementDecision.rule_id == "rule-local")
                .order_by(PlacementDecision.version)
            )
        ).all()
    )
    assert [(item.version, item.rationale) for item in history] == [
        (1, "Initial reviewed placement."),
        (2, "Second reviewed placement."),
    ]


@pytest.mark.asyncio
async def test_placement_uniqueness_race_returns_optimistic_conflict(
    gate1_session: tuple[AsyncSession, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, ids = gate1_session

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    async def conflicting_commit() -> None:
        raise IntegrityError(
            "INSERT INTO placement_decisions ...",
            {},
            RuntimeError("unique rule/version race"),
        )

    monkeypatch.setattr(session, "commit", conflicting_commit)
    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/placement-decisions/{ids['placement_id']}",
                json={
                    "expected_version": 1,
                    "rationale": "A racing reviewed placement.",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 409
    assert response.json()["code"] == "placement_version_conflict"
    assert response.json()["details"]["current_version"] == 2


@pytest.mark.asyncio
async def test_build_inspection_returns_artifact_hashes_and_persisted_spans(
    gate1_session: tuple[AsyncSession, dict[str, str]],
) -> None:
    session, ids = gate1_session

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/builds/{ids['build_id']}/inspection"
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifacts"] == [
        {"path": "prompt-kernel.md", "sha256": ids["artifact_sha256"]}
    ]
    assert payload["generated_spans"][0]["transform_kind"] == "compiler_scaffold"
    assert payload["generated_spans"][0]["source_refs"] == []


@pytest.mark.asyncio
async def test_build_inspection_keeps_legacy_declared_source_maps_readable(
    gate1_session: tuple[AsyncSession, dict[str, str]],
) -> None:
    session, ids = gate1_session
    build = await session.get(Build, ids["build_id"])
    assert build is not None
    build.source_map = {"prompt-kernel.md": ["rule.example"]}
    await session.commit()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/builds/{ids['build_id']}/inspection"
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()["source_map"] == {
        "prompt-kernel.md": ["rule.example"]
    }
