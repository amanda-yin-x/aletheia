from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Build,
    Document,
    Finding,
    GeneratedSpan,
    PlacementDecision,
    Project,
    Rule,
    TestCase,
)
from app.schemas import (
    BuildManifest,
    CompilationMetrics,
    FactFixture,
    InputManifest,
    PolicyArtifact,
    PreservationReport,
    RegressionArtifact,
    RoutingReport,
    RuleIR,
    SourceMapArtifact,
    TestCaseSpec,
    ToolRegistry,
    UnsupportedRulesArtifact,
)
from app.services.canonical import (
    CANONICAL_JSON_DESCRIPTION,
    artifact_hash,
    bytes_hash,
    canonical_json_bytes,
    canonical_json_text,
    token_estimate,
)
from app.services.compilation.metrics import compilation_metrics
from app.services.compilation.profile import LoadedCompilerProfile, load_compiler_profile
from app.services.compilation.provenance import protected_literals, verify_rule_provenance
from app.services.compilation.rendering import SpanWriter, locate_fragment_span
from app.services.errors import ServiceError

COMPILER_VERSION = "1.0.0"
RUNNER_INPUT_VERSION = "0.3.0"
ROOT_ARTIFACT = "manifest.json"
POLICY_ARTIFACT = "policies/tool-policy.json"
TEST_ARTIFACT = "tests/regression.yaml"
TOOL_ARTIFACT = "tools.json"
FACT_ARTIFACT = "facts/evaluation.json"
SOURCE_MAP_ARTIFACT = "source-map.json"
ROUTING_ARTIFACT = "routing-report.json"
PRESERVATION_ARTIFACT = "preservation-report.json"
UNSUPPORTED_ARTIFACT = "pending/unsupported-rules.json"
METRICS_ARTIFACT = "compilation-metrics.json"
PROFILE_INPUT_ARTIFACT = "inputs/compiler-profile.json"
PLACEMENT_INPUT_ARTIFACT = "inputs/placement-decisions.json"
SOURCE_INPUT_ARTIFACT = "inputs/pinned-source-metadata.json"
RULE_INPUT_ARTIFACT = "inputs/rules.json"
FINDING_INPUT_ARTIFACT = "inputs/findings.json"
EVIDENCE_LIMIT = (
    "Artifacts cover reviewed fixture inputs and declared placement decisions; "
    "behavioral fidelity is not measured."
)

DESTINATIONS = frozenset(
    {
        "prompt_kernel",
        "skill",
        "knowledge",
        "pre_tool_policy",
        "test",
        "human_review",
        "unsupported",
    }
)
TRANSFORM_KINDS = frozenset(
    {
        "verbatim",
        "reviewed_normalization",
        "reviewer_authored_guidance",
        "compiler_scaffold",
    }
)
DISPOSITIONS = frozenset({"routed", "blocked", "unsupported", "retired"})
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _json_document(document: Document, purpose: str) -> dict[str, Any]:
    try:
        value = json.loads(document.normalized_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ServiceError(
            "compiler_input_invalid",
            f"The pinned {purpose} document is not valid JSON.",
            details={"document": document.name},
            status_code=409,
        ) from error
    if not isinstance(value, dict):
        raise ServiceError(
            "compiler_input_invalid",
            f"The pinned {purpose} document must contain a JSON object.",
            details={"document": document.name},
            status_code=409,
        )
    return value


def _yaml_text(value: Any) -> str:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
        width=120,
    )


def _configuration(project: Project) -> dict[str, Any]:
    config = project.compilation_config
    required_strings = (
        "bundle_slug",
        "agent_label",
        "skill_title",
        "knowledge_title",
        "suite_name",
    )
    if not isinstance(config, dict) or config.get("schema_version") != "1.0":
        raise ServiceError(
            "compilation_config_missing",
            "The project has no supported compilation configuration.",
            status_code=409,
        )
    for field in required_strings:
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ServiceError(
                "compilation_config_invalid",
                f"The project compilation configuration requires {field}.",
                status_code=409,
            )
    if not isinstance(config.get("suite_version"), int) or config["suite_version"] < 1:
        raise ServiceError(
            "compilation_config_invalid",
            "The project compilation configuration requires a positive suite_version.",
            status_code=409,
        )
    if not SAFE_SLUG.fullmatch(config["bundle_slug"]):
        raise ServiceError(
            "compilation_config_invalid",
            "The configured bundle scope must be a lowercase path-safe slug.",
            status_code=409,
        )
    inputs = config.get("inputs")
    expected_context = config.get("expected_context")
    if not isinstance(inputs, dict) or not isinstance(expected_context, list) or any(
        not isinstance(item, str) or item.startswith("/") or ".." in item.split("/")
        for item in expected_context
    ):
        raise ServiceError(
            "compilation_config_invalid",
            "The project compilation inputs and expected context must be explicitly pinned.",
            status_code=409,
        )
    return config


def _pinned_document(
    documents: list[Document], config: dict[str, Any], purpose: str, *, required: bool
) -> Document | None:
    raw = config["inputs"].get(purpose)
    if raw is None and not required:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not isinstance(raw.get("version"), int):
        raise ServiceError(
            "compiler_input_pin_invalid",
            f"The compilation configuration must pin one {purpose} by name and version.",
            status_code=409,
        )
    matches = [
        item
        for item in documents
        if item.name == raw["name"] and item.version == raw["version"]
    ]
    if len(matches) != 1:
        raise ServiceError(
            "compiler_input_missing",
            f"The pinned {purpose} document is missing or ambiguous.",
            details={"name": raw["name"], "version": raw["version"]},
            status_code=409,
        )
    return matches[0]


def _source_record(
    document: Document, documents_by_id: dict[str, Document]
) -> dict[str, Any]:
    superseded = (
        documents_by_id.get(document.supersedes_document_id)
        if document.supersedes_document_id
        else None
    )
    if document.supersedes_document_id and superseded is None:
        raise ServiceError(
            "authority_link_invalid",
            "A document authority relationship points outside the project snapshot.",
            details={"document": document.name},
            status_code=409,
        )
    return {
        "document_key": f"{document.name}@{document.version}",
        "name": document.name,
        "version": document.version,
        "version_label": document.version_label or str(document.version),
        "kind": document.kind,
        "mime_type": document.mime_type,
        "authority": {
            "owner": document.authority_owner,
            "status": document.authority_status,
            "effective_at": document.effective_at.isoformat() if document.effective_at else None,
            "supersedes_document_key": (
                f"{superseded.name}@{superseded.version}" if superseded else None
            ),
            "jurisdictions": sorted(document.jurisdictions),
            "scopes": sorted(document.authority_scopes),
        },
        "original_sha256": document.original_sha256,
        "normalized_sha256": document.normalized_sha256,
        "line_count": document.line_count,
        "origin": document.origin,
        "normalized_text": document.normalized_text,
    }


def _rule_record(rule: Rule, anchors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "0.2",
        "stable_key": rule.stable_key,
        "revision": rule.revision,
        "title": rule.title,
        "normative_text": rule.normative_text,
        "category": rule.category,
        "effect": rule.effect,
        "severity": rule.severity,
        "status": rule.status,
        "confidence": rule.confidence,
        "scope": rule.scope,
        "condition": rule.condition,
        "requires": rule.requires,
        "exceptions": rule.exceptions,
        "enforcement": rule.enforcement,
        "decidability": rule.decidability,
        "source_refs": [
            {
                "document_name": anchor["document_name"],
                "document_version": anchor["document_version"],
                "line_start": anchor["line_start"],
                "line_end": anchor["line_end"],
                "quote": anchor["quote"],
                "source_sha256": anchor["original_sha256"],
            }
            for anchor in anchors
        ],
        "target_tools": sorted(rule.target_tools),
        "reviewer_note": rule.reviewer_note,
        "provenance_kind": rule.provenance_kind,
        "provenance_metadata": rule.provenance_metadata,
    }


def _finding_record(finding: Finding, rule_keys_by_id: dict[str, str]) -> dict[str, Any]:
    witness = dict(finding.witness)
    resolution = witness.get("resolution")
    if isinstance(resolution, dict):
        stable = {
            key: value
            for key, value in resolution.items()
            if key not in {"winner_rule_id", "loser_rule_id", "actor"}
        }
        winner = resolution.get("winner_rule_id")
        loser = resolution.get("loser_rule_id")
        if isinstance(winner, str) and winner in rule_keys_by_id:
            stable["winner_rule"] = rule_keys_by_id[winner]
        if isinstance(loser, str) and loser in rule_keys_by_id:
            stable["loser_rule"] = rule_keys_by_id[loser]
        witness["resolution"] = stable
    return {
        "type": finding.type,
        "severity": finding.severity,
        "proof_status": finding.proof_status,
        "message": finding.message,
        "witness": witness,
        "related_rules": sorted(
            rule_keys_by_id[item]
            for item in finding.related_rule_ids
            if item in rule_keys_by_id
        ),
        "resolution_state": finding.resolution_state,
        "resolution_note": finding.resolution_note,
    }


def _placement_record(placement: PlacementDecision, rule: Rule) -> dict[str, Any]:
    return {
        "placement_key": f"{rule.stable_key}@{rule.revision}:placement:{placement.version}",
        "rule_key": f"{rule.stable_key}@{rule.revision}",
        "rule_stable_key": rule.stable_key,
        "rule_revision": rule.revision,
        "version": placement.version,
        "profile_name": placement.profile_name,
        "profile_version": placement.profile_version,
        "destinations": sorted(placement.destinations),
        "scope_slug": placement.scope_slug,
        "rendering": placement.rendering,
        "transform_kind": placement.transform_kind,
        "disposition": placement.disposition,
        "rationale": placement.rationale,
        "review_status": placement.review_status,
        "reviewer": placement.reviewer,
    }


def _validate_placement(
    rule: Rule,
    placement: PlacementDecision,
    profile: LoadedCompilerProfile,
    linked_tests: list[TestCase],
) -> None:
    destinations = placement.destinations
    profile_destinations = set(profile.value["allowed_destinations"])
    if not isinstance(destinations, list) or not destinations or any(
        item not in DESTINATIONS or item not in profile_destinations
        for item in destinations
    ) or len(destinations) != len(set(destinations)):
        raise ServiceError(
            "placement_destination_unknown",
            "Every active clause requires known, unique compilation destinations.",
            details={"rule": rule.stable_key, "destinations": destinations},
            status_code=409,
        )
    if placement.profile_name != profile.name or placement.profile_version != profile.version:
        raise ServiceError(
            "placement_profile_mismatch",
            "A placement decision was reviewed against a different compiler profile.",
            details={"rule": rule.stable_key},
            status_code=409,
        )
    if placement.transform_kind not in TRANSFORM_KINDS or placement.disposition not in DISPOSITIONS:
        raise ServiceError(
            "placement_contract_invalid",
            "A placement decision uses an unknown transform or disposition.",
            details={"rule": rule.stable_key},
            status_code=409,
        )
    if placement.disposition == "unsupported" and destinations != ["unsupported"]:
        raise ServiceError(
            "placement_contract_invalid",
            "Unsupported clauses must remain only in the unsupported ledger.",
            details={"rule": rule.stable_key},
            status_code=409,
        )
    if placement.disposition == "routed" and set(destinations) & {"unsupported", "human_review"}:
        raise ServiceError(
            "placement_contract_invalid",
            "Routed clauses cannot also be labelled unsupported or pending human review.",
            details={"rule": rule.stable_key},
            status_code=409,
        )
    if rule.status == "approved" and placement.disposition == "routed" and placement.review_status != "approved":
        raise ServiceError(
            "placement_review_required",
            "An approved clause has an unreviewed placement decision.",
            details={"rule": rule.stable_key},
            status_code=409,
        )
    if rule.status != "approved" and placement.disposition == "routed":
        raise ServiceError(
            "unreviewed_clause_routed",
            "An unapproved clause cannot enter compiled execution artifacts.",
            details={"rule": rule.stable_key, "status": rule.status},
            status_code=409,
        )
    if placement.rendering and placement.rendering != rule.normative_text:
        if placement.transform_kind != "reviewed_normalization" or placement.review_status != "approved" or not placement.reviewer.strip() or not placement.rationale.strip():
            raise ServiceError(
                "placement_rendering_unreviewed",
                "A changed rendering requires an approved reviewed-normalization decision.",
                details={"rule": rule.stable_key},
                status_code=409,
            )
    if "test" in destinations and not linked_tests:
        raise ServiceError(
            "placement_test_missing",
            "A test placement has no approved build-pinned test linked to the rule.",
            details={"rule": rule.stable_key},
            status_code=409,
        )
    if rule.status == "approved" and rule.category == "hard_constraint" and rule.severity in {"high", "critical"}:
        required = {"pre_tool_policy", "test"}
        if not required.issubset(set(destinations)):
            raise ServiceError(
                "critical_placement_incomplete",
                "Approved high- and critical-severity hard rules require guard and test placement.",
                details={"rule": rule.stable_key, "missing": sorted(required - set(destinations))},
                status_code=409,
            )


def _markdown_artifact(
    path: str,
    title: str,
    intro: str,
    rows: list[tuple[Rule, PlacementDecision, list[dict[str, Any]], str]],
    *,
    skill: bool = False,
    scope_slug: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    writer = SpanWriter(path)
    if skill:
        writer.scaffold(
            f"---\nname: {scope_slug}\ndescription: Reviewed, source-linked instructions for this scope.\n---\n\n"
        )
    writer.scaffold(f"# {title}\n\n{intro}\n\n")
    writer.scaffold("## Reviewed clauses\n\n")
    if not rows:
        writer.scaffold("No reviewed clauses are routed to this artifact.\n")
    for rule, placement, anchors, transform in rows:
        writer.bullet(
            placement.rendering or rule.normative_text,
            transform_kind=transform,
            rule=rule,
            placement=placement,
            source_refs=anchors,
        )
    return writer.finish()


def _stable_test_records(tests: list[TestCase]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for test in tests:
        try:
            spec = TestCaseSpec.model_validate(test.spec).model_dump(mode="json", by_alias=True)
        except ValidationError as error:
            raise ServiceError(
                "compiler_test_contract_invalid",
                "An approved test does not satisfy the versioned test contract.",
                details={"test": test.stable_key, "errors": error.errors(include_url=False)},
                status_code=409,
            ) from error
        records.append(
            {
                "stable_key": test.stable_key,
                "title": test.title,
                "provenance": test.provenance,
                "review_status": test.review_status,
                "spec": spec,
            }
        )
    return records


async def compile_project(session: AsyncSession, project_id: str) -> Build:
    project = await session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None:
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    config = _configuration(project)
    profile = load_compiler_profile(project.compiler_profile)
    findings = list(
        (
            await session.scalars(
                select(Finding)
                .where(Finding.project_id == project_id)
                .order_by(Finding.type, Finding.severity, Finding.message)
            )
        ).all()
    )
    blocking_findings = [
        finding
        for finding in findings
        if finding.severity == "critical" and finding.resolution_state == "open"
    ]
    if blocking_findings:
        raise ServiceError(
            "critical_findings_unresolved",
            "Resolve critical policy conflicts before building a candidate.",
            details={"finding_ids": [item.id for item in blocking_findings]},
            status_code=409,
        )
    documents = list(
        (
            await session.scalars(
                select(Document)
                .where(Document.project_id == project_id)
                .order_by(Document.name, Document.version, Document.kind)
            )
        ).all()
    )
    all_rules = list(
        (
            await session.scalars(
                select(Rule)
                .where(Rule.project_id == project_id)
                .order_by(Rule.stable_key, Rule.revision)
            )
        ).all()
    )
    active_rules = [rule for rule in all_rules if rule.status != "superseded"]
    unreviewed_critical = [
        rule
        for rule in active_rules
        if rule.severity in {"high", "critical"} and rule.status not in {"approved", "rejected"}
    ]
    if unreviewed_critical:
        raise ServiceError(
            "critical_rules_unreviewed",
            "Review every active high- or critical-severity clause before compilation.",
            details={"rules": [f"{item.stable_key}@{item.revision}" for item in unreviewed_critical]},
            status_code=409,
        )
    tests = list(
        (
            await session.scalars(
                select(TestCase)
                .where(TestCase.project_id == project_id, TestCase.review_status == "approved")
                .order_by(TestCase.stable_key)
            )
        ).all()
    )
    placements = list(
        (
            await session.scalars(
                select(PlacementDecision)
                .where(PlacementDecision.project_id == project_id)
                .order_by(PlacementDecision.rule_id, PlacementDecision.version.desc())
            )
        ).all()
    )
    latest_placement: dict[str, PlacementDecision] = {}
    for placement in placements:
        latest_placement.setdefault(placement.rule_id, placement)
    missing_placements = [rule for rule in active_rules if rule.id not in latest_placement]
    if missing_placements:
        raise ServiceError(
            "placement_decision_missing",
            "Every active normative clause needs an explicit placement or unsupported disposition.",
            details={"rules": [f"{item.stable_key}@{item.revision}" for item in missing_placements]},
            status_code=409,
        )
    documents_by_id = {item.id: item for item in documents}
    tests_by_rule: dict[str, list[TestCase]] = defaultdict(list)
    for test in tests:
        spec_rule_ids = test.spec.get("rule_ids", []) if isinstance(test.spec, dict) else []
        for stable_key in spec_rule_ids:
            if isinstance(stable_key, str):
                tests_by_rule[stable_key].append(test)
    anchors_by_rule: dict[str, list[dict[str, Any]]] = {}
    transforms_by_rule: dict[str, str] = {}
    for rule in active_rules:
        anchors, inferred_transform = verify_rule_provenance(
            rule,
            documents_by_id,
            require_verified=rule.status == "approved",
        )
        placement = latest_placement[rule.id]
        _validate_placement(rule, placement, profile, tests_by_rule[rule.stable_key])
        if placement.transform_kind == "reviewer_authored_guidance":
            inferred_transform = placement.transform_kind
        elif placement.rendering and placement.rendering != rule.normative_text:
            inferred_transform = "reviewed_normalization"
        if inferred_transform != placement.transform_kind:
            raise ServiceError(
                "placement_transform_mismatch",
                "The reviewed transform kind does not match the rule provenance and rendering.",
                details={"rule": rule.stable_key, "expected": inferred_transform},
                status_code=409,
            )
        if placement.disposition == "routed" and any(
            anchor["authority_status"] == "superseded" for anchor in anchors
        ):
            raise ServiceError(
                "stale_authority_routed",
                "A routed clause is anchored only to a superseded authority source.",
                details={"rule": rule.stable_key},
                status_code=409,
            )
        anchors_by_rule[rule.id] = anchors
        transforms_by_rule[rule.id] = inferred_transform

    baseline_document = _pinned_document(documents, config, "baseline_prompt", required=False)
    tool_document = _pinned_document(documents, config, "tool_schema", required=True)
    fact_document = _pinned_document(documents, config, "evaluation_data", required=True)
    assert tool_document is not None and fact_document is not None
    baseline = baseline_document.normalized_text if baseline_document else ""
    try:
        tools = ToolRegistry.model_validate(
            _json_document(tool_document, "tool registry")
        ).model_dump(mode="json", by_alias=True, exclude_unset=True)
        facts = FactFixture.model_validate(
            _json_document(fact_document, "evaluation data")
        ).model_dump(mode="json", by_alias=True, exclude_unset=True)
    except ValidationError as error:
        raise ServiceError(
            "compiler_fixture_contract_invalid",
            "A pinned tool or evaluation fixture violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error

    try:
        rule_records = {
            rule.id: RuleIR.model_validate(
                _rule_record(rule, anchors_by_rule[rule.id])
            ).model_dump(mode="json", by_alias=True)
            for rule in active_rules
        }
    except ValidationError as error:
        raise ServiceError(
            "compiler_rule_contract_invalid",
            "A reviewed rule does not satisfy the versioned compiler contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    test_records = _stable_test_records(tests)
    rows_by_destination: dict[
        str, list[tuple[Rule, PlacementDecision, list[dict[str, Any]], str]]
    ] = defaultdict(list)
    routing_entries: list[dict[str, Any]] = []
    unsupported_entries: list[dict[str, Any]] = []
    for rule in active_rules:
        placement = latest_placement[rule.id]
        anchors = anchors_by_rule[rule.id]
        transform = transforms_by_rule[rule.id]
        destinations = sorted(placement.destinations)
        entry = {
            "rule_key": f"{rule.stable_key}@{rule.revision}",
            "rule_stable_key": rule.stable_key,
            "rule_revision": rule.revision,
            "title": rule.title,
            "rule_status": rule.status,
            "severity": rule.severity,
            "category": rule.category,
            "provenance_kind": rule.provenance_kind,
            "provenance_metadata": rule.provenance_metadata,
            "verified_source_anchors": len(anchors),
            "source_anchors": anchors,
            "placement": _placement_record(placement, rule),
            "destinations": destinations,
            "disposition": placement.disposition,
            "rationale": placement.rationale,
        }
        routing_entries.append(entry)
        if placement.disposition == "routed":
            for destination in destinations:
                rows_by_destination[destination].append((rule, placement, anchors, transform))
        elif placement.disposition in {"unsupported", "blocked"}:
            unsupported_entries.append(
                {
                    **entry,
                    "normative_text": rule.normative_text,
                    "reason": placement.rationale or "Pending explicit review or clarification.",
                }
            )

    scope_slug = config["bundle_slug"]
    skill_path = f"skills/{scope_slug}/SKILL.md"
    knowledge_path = f"knowledge/{scope_slug}.md"
    prompt, prompt_spans = _markdown_artifact(
        "prompt-kernel.md",
        config["agent_label"],
        "Keep this kernel always loaded. Load scoped skills and references only when their task applies.",
        rows_by_destination["prompt_kernel"],
    )
    skill, skill_spans = _markdown_artifact(
        skill_path,
        config["skill_title"],
        "Apply these reviewed clauses before proposing or describing covered actions.",
        rows_by_destination["skill"],
        skill=True,
        scope_slug=scope_slug,
    )
    knowledge, knowledge_spans = _markdown_artifact(
        knowledge_path,
        config["knowledge_title"],
        "Use this reference only for the scoped task; current authority decisions remain controlling.",
        rows_by_destination["knowledge"],
    )
    guarded_rule_ids = {row[0].id for row in rows_by_destination["pre_tool_policy"]}
    raw_policy = {
        "schema_version": "0.2",
        "default_decision": "allow",
        "scope_statement": (
            "Decisions apply only to reviewed rules and tool calls routed through this adapter."
        ),
        "rules": [
            rule_records[rule.id]
            for rule in active_rules
            if rule.id in guarded_rule_ids
        ],
    }
    raw_regression = {
        "schema_version": "0.2",
        "suite": {
            "name": config["suite_name"],
            "version": str(config["suite_version"]),
            "data_scope": "evaluation",
            "provenance": "aletheia_reviewed_fixture",
        },
        "tests": test_records,
    }
    try:
        policy = PolicyArtifact.model_validate(raw_policy).model_dump(mode="json", by_alias=True)
        regression = RegressionArtifact.model_validate(raw_regression).model_dump(mode="json", by_alias=True)
    except ValidationError as error:
        raise ServiceError(
            "compiler_artifact_contract_invalid",
            "A policy or regression artifact does not satisfy its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    policy_text = canonical_json_text(policy)
    regression_text = _yaml_text(regression)
    unsupported_payload = {
        "schema_version": "1.0",
        "rules": unsupported_entries,
        "interpretation": "Unsupported or pending clauses are visible and are not emitted into the deterministic guard.",
    }
    unsupported_text = canonical_json_text(unsupported_payload)
    generated_spans = [*prompt_spans, *skill_spans, *knowledge_spans]
    search_from = 0
    for rule, placement, anchors, transform in rows_by_destination["pre_tool_policy"]:
        fragment = canonical_json_text(rule_records[rule.id]).strip()
        span, search_from = locate_fragment_span(
            POLICY_ARTIFACT,
            policy_text,
            fragment,
            transform_kind=transform,
            rule=rule,
            placement=placement,
            source_refs=anchors,
            start_at=search_from,
        )
        generated_spans.append(span)
    for test in tests:
        marker = f"stable_key: {test.stable_key}"
        marker_start = 0
        for rule in active_rules:
            placement = latest_placement[rule.id]
            if "test" not in placement.destinations or test not in tests_by_rule[rule.stable_key]:
                continue
            span, marker_start = locate_fragment_span(
                TEST_ARTIFACT,
                regression_text,
                marker,
                transform_kind="compiler_scaffold",
                rule=rule,
                placement=placement,
                source_refs=[],
                start_at=marker_start,
            )
            generated_spans.append(span)
            marker_start = 0
    unsupported_search = 0
    for item in unsupported_entries:
        rule = next(rule for rule in active_rules if item["rule_key"] == f"{rule.stable_key}@{rule.revision}")
        placement = latest_placement[rule.id]
        fragment = json.dumps(item["normative_text"], ensure_ascii=False)[1:-1]
        span, unsupported_search = locate_fragment_span(
            UNSUPPORTED_ARTIFACT,
            unsupported_text,
            fragment,
            transform_kind=transforms_by_rule[rule.id],
            rule=rule,
            placement=placement,
            source_refs=anchors_by_rule[rule.id],
            start_at=unsupported_search,
        )
        generated_spans.append(span)

    source_records = [
        _source_record(document, documents_by_id) for document in documents
    ]
    finding_keys = {rule.id: f"{rule.stable_key}@{rule.revision}" for rule in all_rules}
    finding_records = [_finding_record(item, finding_keys) for item in findings]
    placement_records = [
        _placement_record(latest_placement[rule.id], rule) for rule in active_rules
    ]
    routing_report = {
        "schema_version": "1.0",
        "profile": {"name": profile.name, "version": profile.version, "sha256": profile.digest},
        "entries": routing_entries,
        "counts": {
            "active": len(routing_entries),
            "routed": sum(item["disposition"] == "routed" for item in routing_entries),
            "blocked": sum(item["disposition"] == "blocked" for item in routing_entries),
            "unsupported": sum(item["disposition"] == "unsupported" for item in routing_entries),
        },
    }
    artifacts: dict[str, str] = {
        "prompt-kernel.md": prompt,
        skill_path: skill,
        knowledge_path: knowledge,
        POLICY_ARTIFACT: policy_text,
        TEST_ARTIFACT: regression_text,
        TOOL_ARTIFACT: canonical_json_text(tools),
        FACT_ARTIFACT: canonical_json_text(facts),
        UNSUPPORTED_ARTIFACT: unsupported_text,
        ROUTING_ARTIFACT: canonical_json_text(routing_report),
        PROFILE_INPUT_ARTIFACT: canonical_json_text(
            {"schema_version": "1.0", "profile": profile.value, "sha256": profile.digest}
        ),
        PLACEMENT_INPUT_ARTIFACT: canonical_json_text(
            {"schema_version": "1.0", "placements": placement_records}
        ),
        SOURCE_INPUT_ARTIFACT: canonical_json_text(
            {"schema_version": "1.0", "sources": source_records}
        ),
        RULE_INPUT_ARTIFACT: canonical_json_text(
            {"schema_version": "1.0", "rules": [rule_records[item.id] for item in active_rules]}
        ),
        FINDING_INPUT_ARTIFACT: canonical_json_text(
            {"schema_version": "1.0", "findings": finding_records}
        ),
    }
    literal_checks: list[dict[str, Any]] = []
    destination_paths = {
        "prompt_kernel": ["prompt-kernel.md"],
        "skill": [skill_path],
        "knowledge": [knowledge_path],
        "pre_tool_policy": [POLICY_ARTIFACT],
        "test": [TEST_ARTIFACT],
        "unsupported": [UNSUPPORTED_ARTIFACT],
        "human_review": [UNSUPPORTED_ARTIFACT],
    }
    for rule in active_rules:
        placement = latest_placement[rule.id]
        rendering = placement.rendering or rule.normative_text
        literals = protected_literals(rendering, sorted(rule.target_tools))
        paths = sorted(
            {
                path
                for destination in placement.destinations
                for path in destination_paths.get(destination, [])
            }
        )
        corpus = "\n".join(artifacts[path] for path in paths if path in artifacts)
        missing = [item for item in literals if item["value"] not in corpus]
        literal_checks.append(
            {
                "rule_key": f"{rule.stable_key}@{rule.revision}",
                "artifact_paths": paths,
                "literals": literals,
                "missing": missing,
                "preserved": not missing and rendering in corpus,
            }
        )
    preservation_report = {
        "schema_version": "1.0",
        "checks": literal_checks,
        "behavioral_fidelity": "not_measured",
        "interpretation": (
            "Exact rendering and protected-literal checks are deterministic conformance checks; they do not establish semantic equivalence or behavioral fidelity."
        ),
    }
    artifacts[PRESERVATION_ARTIFACT] = canonical_json_text(preservation_report)
    metrics = compilation_metrics(
        baseline=baseline,
        artifacts=artifacts,
        kernel_path="prompt-kernel.md",
        skill_paths=[skill_path],
        knowledge_paths=[knowledge_path],
        machine_paths=[POLICY_ARTIFACT, TEST_ARTIFACT],
        expected_context_paths=config["expected_context"],
        routing_entries=routing_entries,
        literal_checks=literal_checks,
    )
    artifacts[METRICS_ARTIFACT] = canonical_json_text(metrics)
    source_map: dict[str, Any] = {
        "schema_version": "1.0",
        "range_convention": "1-based inclusive lines; 0-based half-open UTF-8 byte ranges",
        "spans": sorted(
            generated_spans,
            key=lambda item: (
                item["artifact_path"],
                item["utf8_byte_start"],
                item.get("rule_id") or "",
            ),
        ),
    }
    artifacts[SOURCE_MAP_ARTIFACT] = canonical_json_text(source_map)
    try:
        RoutingReport.model_validate(routing_report)
        PreservationReport.model_validate(preservation_report)
        CompilationMetrics.model_validate(metrics)
        SourceMapArtifact.model_validate(source_map)
        UnsupportedRulesArtifact.model_validate(unsupported_payload)
    except ValidationError as error:
        raise ServiceError(
            "compiler_gate1_artifact_invalid",
            "A Gate 1 routing, preservation, metric, or source-map artifact violates its contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    readme = (
        "# Compiled instruction bundle\n\n"
        "This byte-addressed bundle was produced from reviewed source anchors and explicit placement decisions.\n\n"
        "- `prompt-kernel.md` is the always-loaded kernel.\n"
        f"- `{skill_path}` is the scoped instruction skill.\n"
        f"- `{knowledge_path}` is the scoped knowledge reference.\n"
        "- `policies/tool-policy.json` contains the bounded pre-tool policy.\n"
        "- `routing-report.json`, `preservation-report.json`, and `source-map.json` make disposition and provenance inspectable.\n"
        "- `pending/unsupported-rules.json` keeps unresolved language visible and out of the guard.\n\n"
        "Deterministic conformance does not measure behavioral fidelity.\n"
    )
    artifacts["README.md"] = readme
    artifact_hashes = {path: artifact_hash(value) for path, value in sorted(artifacts.items())}
    source_inputs = [
        {
            "name": item["name"],
            "version": item["version"],
            "kind": item["kind"],
            "original_sha256": item["original_sha256"],
            "normalized_sha256": item["normalized_sha256"],
            "parser": item["origin"].get("parser", "unspecified"),
            "parser_version": item["origin"].get("parser_version", "unspecified"),
            "normalizer": item["origin"].get("normalizer", "unspecified"),
            "normalizer_version": item["origin"].get("normalizer_version", "unspecified"),
        }
        for item in source_records
    ]
    rule_inputs = [
        {
            "stable_key": record["stable_key"],
            "revision": record["revision"],
            "status": record["status"],
            "severity": record["severity"],
            "category": record["category"],
            "enforcement": record["enforcement"],
            "provenance_kind": record["provenance_kind"],
            "provenance_metadata": record["provenance_metadata"],
            "source_documents": sorted(
                {ref["document_name"] for ref in record["source_refs"]}
            ),
            "digest": artifact_hash(record),
        }
        for record in rule_records.values()
    ]
    test_inputs = [
        {
            "stable_key": item["stable_key"],
            "title": item["title"],
            "provenance": item["provenance"],
            "rule_ids": sorted(item["spec"]["rule_ids"]),
            "tags": sorted(item["spec"]["tags"]),
            "digest": artifact_hash(item["spec"]),
        }
        for item in test_records
    ]
    unresolved = [item for item in finding_records if item["resolution_state"] == "open"]
    accepted = [item for item in finding_records if item["resolution_state"] != "open"]
    raw_input_manifest = {
        "schema_version": "1.0",
        "compiler": {
            "name": "aletheia-source-aware-compiler",
            "version": COMPILER_VERSION,
            "serialization": CANONICAL_JSON_DESCRIPTION,
            "token_estimator": "char_div_4_v1",
        },
        "runtime": {
            "adapter": "deterministic_replay",
            "runner_input_version": RUNNER_INPUT_VERSION,
            "policy_schema_version": policy["schema_version"],
            "domain": project.domain,
            "lifecycle": "pre_tool",
            "arms": ["baseline_unenforced", "compiled_unenforced", "compiled_enforced"],
        },
        "sources": source_inputs,
        "rules": rule_inputs,
        "tests": test_inputs,
        "tools": {
            "source": tool_document.name,
            "source_sha256": tool_document.original_sha256,
            "artifact": TOOL_ARTIFACT,
            "artifact_sha256": artifact_hashes[TOOL_ARTIFACT],
        },
        "facts": {
            "source": fact_document.name,
            "source_sha256": fact_document.original_sha256,
            "artifact": FACT_ARTIFACT,
            "artifact_sha256": artifact_hashes[FACT_ARTIFACT],
            "data_scope": facts.get("data_scope", "unspecified"),
            "contains_customer_records": facts.get("contains_customer_records", False),
        },
        "findings": {"unresolved": unresolved, "accepted": accepted},
        "compiler_profile": {
            "name": profile.name,
            "version": profile.version,
            "path": profile.path,
            "digest": profile.digest,
        },
        "placements": [
            {**item, "digest": artifact_hash(item)} for item in placement_records
        ],
        "compilation_config_digest": artifact_hash(config),
    }
    try:
        input_manifest = InputManifest.model_validate(raw_input_manifest).model_dump(
            mode="json", by_alias=True
        )
    except ValidationError as error:
        raise ServiceError(
            "compiler_input_contract_invalid",
            "The pinned build inputs do not satisfy the versioned manifest contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    raw_manifest = {
        "schema_version": "1.0",
        "compiler_version": COMPILER_VERSION,
        "serialization": {
            "json": CANONICAL_JSON_DESCRIPTION,
            "text_and_yaml": "exact UTF-8 bytes; final LF is significant",
            "hash_algorithm": "sha256",
        },
        "inputs": input_manifest,
        "input_hash": bytes_hash(canonical_json_bytes(input_manifest)),
        "artifact_hashes": artifact_hashes,
        "artifact_root": {
            "members": sorted(artifact_hashes),
            "excluded": [ROOT_ARTIFACT],
            "exclusion_reason": "The manifest excludes itself to avoid a recursive digest.",
        },
        "unresolved_findings": unresolved,
        "accepted_findings": accepted,
        "limitations": [
            EVIDENCE_LIMIT,
            "Deterministic compilation does not establish live-model quality or behavioral fidelity.",
        ],
    }
    try:
        manifest = BuildManifest.model_validate(raw_manifest).model_dump(
            mode="json", by_alias=True
        )
    except ValidationError as error:
        raise ServiceError(
            "compiler_manifest_contract_invalid",
            "The compiled build root does not satisfy its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_hash = bytes_hash(manifest_bytes)
    artifacts[ROOT_ARTIFACT] = manifest_bytes.decode("utf-8")
    legacy_stats = {
        "original": {
            "lines": len(baseline.splitlines()),
            "characters": len(baseline),
            "tokens": token_estimate(baseline),
        },
        "candidate": {
            "lines": len(prompt.splitlines()),
            "characters": len(prompt),
            "tokens": token_estimate(prompt),
        },
        "reduction": {
            "lines": len(baseline.splitlines()) - len(prompt.splitlines()),
            "characters": len(baseline) - len(prompt),
            "estimated_tokens": token_estimate(baseline) - token_estimate(prompt),
            "label": "char_div_4_v1",
        },
        "routing": {
            "kept_in_prompt": len(rows_by_destination["prompt_kernel"]),
            "moved_to_workflow": len(rows_by_destination["skill"]),
            "guarded": len(rows_by_destination["pre_tool_policy"]),
            "tested": len(tests),
        },
    }
    stats = {**legacy_stats, "compilation": metrics}
    existing = await session.scalar(
        select(Build).where(Build.project_id == project_id, Build.content_hash == manifest_hash)
    )
    if existing:
        return existing
    build = Build(
        project_id=project_id,
        status="succeeded",
        input_manifest=input_manifest,
        input_hash=manifest["input_hash"],
        compiler_version=COMPILER_VERSION,
        artifacts=artifacts,
        source_map=source_map,
        stats=stats,
        content_hash=manifest_hash,
    )
    session.add(build)
    await session.flush()
    await session.execute(delete(GeneratedSpan).where(GeneratedSpan.build_id == build.id))
    rules_by_stable_revision = {
        f"{rule.stable_key}@{rule.revision}": rule for rule in active_rules
    }
    placement_by_stable = {
        f"{rule.stable_key}@{rule.revision}:placement:{latest_placement[rule.id].version}": latest_placement[rule.id]
        for rule in active_rules
    }
    for item in source_map["spans"]:
        span_rule = rules_by_stable_revision.get(item.get("rule_id"))
        span_placement = placement_by_stable.get(item.get("placement_decision_id"))
        session.add(
            GeneratedSpan(
                build_id=build.id,
                rule_id=span_rule.id if span_rule else None,
                placement_decision_id=(
                    span_placement.id if span_placement else None
                ),
                artifact_path=item["artifact_path"],
                artifact_sha256=item["artifact_sha256"],
                line_start=item["line_start"],
                line_end=item["line_end"],
                utf8_byte_start=item["utf8_byte_start"],
                utf8_byte_end=item["utf8_byte_end"],
                transform_kind=item["transform_kind"],
                text_sha256=item["text_sha256"],
                source_refs=item["source_refs"],
            )
        )
    await session.commit()
    await session.refresh(build)
    return build
