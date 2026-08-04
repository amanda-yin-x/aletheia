from __future__ import annotations

import json
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Build, Document, Finding, Project, Rule, TestCase
from app.schemas import (
    BuildManifest,
    FactFixture,
    InputManifest,
    PolicyArtifact,
    RegressionArtifact,
    RuleIR,
    TestCaseSpec,
    ToolRegistry,
)
from app.services.canonical import (
    CANONICAL_JSON_DESCRIPTION,
    artifact_hash,
    bytes_hash,
    canonical_json_bytes,
    canonical_json_text,
    token_estimate,
)
from app.services.errors import ServiceError

COMPILER_VERSION = "0.3.0"
RUNNER_INPUT_VERSION = "0.3.0"
EVIDENCE_LIMIT = (
    "Artifacts and results cover only the reviewed rules, fixture trajectories, "
    "and tool calls routed through this policy adapter."
)
ROOT_ARTIFACT = "manifest.json"
POLICY_ARTIFACT = "policies/tool-policy.json"
TEST_ARTIFACT = "tests/regression.yaml"
TOOL_ARTIFACT = "tools.json"
FACT_ARTIFACT = "facts/orders.json"


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


def _source_record(document: Document) -> dict[str, Any]:
    return {
        "name": document.name,
        "version": document.version,
        "kind": document.kind,
        "mime_type": document.mime_type,
        "original_sha256": document.original_sha256,
        "normalized_sha256": document.normalized_sha256,
        "line_count": document.line_count,
        "origin": document.origin,
        "normalized_text": document.normalized_text,
    }


def _stable_source_refs(
    rule: Rule, documents_by_id: dict[str, Document]
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in rule.source_refs:
        document = documents_by_id.get(str(ref.get("document_id", "")))
        refs.append(
            {
                "document_name": (
                    document.name if document is not None else ref.get("document_name")
                ),
                "document_version": document.version if document is not None else None,
                "line_start": ref.get("line_start"),
                "line_end": ref.get("line_end"),
                "quote": ref.get("quote"),
                "source_sha256": ref.get("source_sha256"),
            }
        )
    return sorted(
        refs,
        key=lambda item: (
            str(item.get("document_name")),
            int(item.get("document_version") or 0),
            int(item.get("line_start") or 0),
        ),
    )


def _rule_record(rule: Rule, documents_by_id: dict[str, Document]) -> dict[str, Any]:
    return {
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
        "enforcement": rule.enforcement,
        "decidability": rule.decidability,
        "source_refs": _stable_source_refs(rule, documents_by_id),
        "target_tools": sorted(rule.target_tools),
        "exceptions": rule.exceptions,
        "reviewer_note": rule.reviewer_note,
    }


def _finding_record(
    finding: Finding, rule_keys_by_id: dict[str, str]
) -> dict[str, Any]:
    witness = dict(finding.witness)
    resolution = witness.get("resolution")
    if isinstance(resolution, dict):
        stable_resolution = {
            key: value
            for key, value in resolution.items()
            if key
            not in {
                "winner_rule_id",
                "loser_rule_id",
                "actor",
            }
        }
        winner_id = resolution.get("winner_rule_id")
        loser_id = resolution.get("loser_rule_id")
        if isinstance(winner_id, str) and winner_id in rule_keys_by_id:
            stable_resolution["winner_rule"] = rule_keys_by_id[winner_id]
        if isinstance(loser_id, str) and loser_id in rule_keys_by_id:
            stable_resolution["loser_rule"] = rule_keys_by_id[loser_id]
        witness["resolution"] = stable_resolution
    return {
        "type": finding.type,
        "severity": finding.severity,
        "proof_status": finding.proof_status,
        "message": finding.message,
        "witness": witness,
        "related_rules": sorted(
            {
                rule_keys_by_id[rule_id]
                for rule_id in finding.related_rule_ids
                if rule_id in rule_keys_by_id
            }
        ),
        "resolution_state": finding.resolution_state,
        "resolution_note": finding.resolution_note,
    }


def _yaml_text(value: Any) -> str:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
        width=120,
    )


def _select_pinned_document(
    documents: list[Document], kind: str, *, required: bool
) -> Document | None:
    """Select the highest explicit version and reject an ambiguous version tie."""

    candidates = [document for document in documents if document.kind == kind]
    if not candidates:
        if required:
            raise ServiceError(
                "compiler_input_missing",
                f"The build requires one pinned {kind} document.",
                details={"missing_kinds": [kind]},
                status_code=409,
            )
        return None
    highest_version = max(document.version for document in candidates)
    selected = [
        document for document in candidates if document.version == highest_version
    ]
    if len(selected) != 1:
        raise ServiceError(
            "compiler_input_ambiguous",
            f"More than one {kind} document has the selected version.",
            details={
                "kind": kind,
                "version": highest_version,
                "documents": sorted(document.name for document in selected),
            },
            status_code=409,
        )
    return selected[0]


async def compile_project(session: AsyncSession, project_id: str) -> Build:
    project = await session.get(Project, project_id)
    if project is None:
        raise ServiceError(
            "project_not_found", "Project not found.", status_code=404
        )
    findings = list(
        (
            await session.scalars(
                select(Finding)
                .where(Finding.project_id == project_id)
                .order_by(Finding.type, Finding.severity, Finding.message)
            )
        ).all()
    )
    blocking = [
        finding
        for finding in findings
        if finding.severity == "critical" and finding.resolution_state == "open"
    ]
    if blocking:
        raise ServiceError(
            "critical_findings_unresolved",
            "Resolve critical policy conflicts before building a candidate.",
            details={
                "finding_ids": [finding.id for finding in blocking],
                "messages": [finding.message for finding in blocking],
            },
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
    approved = [rule for rule in active_rules if rule.status == "approved"]
    tests = list(
        (
            await session.scalars(
                select(TestCase)
                .where(
                    TestCase.project_id == project_id,
                    TestCase.review_status == "approved",
                )
                .order_by(TestCase.stable_key)
            )
        ).all()
    )
    documents_by_id = {document.id: document for document in documents}
    rule_keys_by_id = {
        rule.id: f"{rule.stable_key}@{rule.revision}" for rule in all_rules
    }
    source_records = [_source_record(document) for document in documents]
    try:
        rule_records = [
            RuleIR.model_validate(_rule_record(rule, documents_by_id)).model_dump(
                mode="json", by_alias=True
            )
            for rule in active_rules
        ]
    except ValidationError as error:
        raise ServiceError(
            "compiler_rule_contract_invalid",
            "A reviewed rule does not satisfy the versioned compiler contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    finding_records = [
        _finding_record(finding, rule_keys_by_id) for finding in findings
    ]
    try:
        test_records: list[dict[str, Any]] = [
            {
                "stable_key": test.stable_key,
                "title": test.title,
                "provenance": test.provenance,
                "review_status": test.review_status,
                "spec": TestCaseSpec.model_validate(test.spec).model_dump(
                    mode="json", by_alias=True
                ),
            }
            for test in tests
        ]
    except ValidationError as error:
        raise ServiceError(
            "compiler_test_contract_invalid",
            "An approved test does not satisfy the versioned test contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error

    baseline_document = _select_pinned_document(
        documents, "baseline_prompt", required=False
    )
    baseline = baseline_document.normalized_text if baseline_document else ""
    tool_document = _select_pinned_document(documents, "tool_schema", required=True)
    fact_document = _select_pinned_document(
        documents, "evaluation_data", required=True
    )
    assert tool_document is not None and fact_document is not None
    try:
        tools = ToolRegistry.model_validate(
            _json_document(tool_document, "tool registry")
        ).model_dump(mode="json", by_alias=True, exclude_unset=True)
        facts = FactFixture.model_validate(
            _json_document(fact_document, "fact fixture")
        ).model_dump(mode="json", by_alias=True, exclude_unset=True)
    except ValidationError as error:
        raise ServiceError(
            "compiler_fixture_contract_invalid",
            "A pinned tool or fact fixture violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error

    style_rules = [rule for rule in approved if rule.category == "style"]
    hard_rules = [rule for rule in approved if rule.category == "hard_constraint"]
    workflow_rules = [
        rule for rule in approved if rule.category in {"workflow", "handoff"}
    ]
    knowledge_rules = [rule for rule in approved if rule.category == "knowledge"]
    guarded = [
        rule
        for rule in hard_rules
        if rule.enforcement == "guard" and rule.decidability == "machine_decidable"
    ]
    reference_rules = [
        *knowledge_rules,
        *[
            rule
            for rule in hard_rules
            if "window" in rule.stable_key.lower() or "window" in rule.title.lower()
        ],
    ]

    prompt_lines = [
        "# Northstar Retail support kernel",
        "",
        "You are Northstar Retail's concise, empathetic customer-support agent.",
        "Route refund requests to the scoped refund workflow before calling tools.",
        "Never describe a proposed call as executed or claim success before a tool result.",
        "",
        "## Covered constraints",
    ]
    prompt_lines.extend(f"- {rule.normative_text}" for rule in hard_rules)
    prompt_lines.extend(["", "## Style"])
    prompt_lines.extend(f"- {rule.normative_text}" for rule in style_rules)
    prompt = "\n".join(prompt_lines).strip() + "\n"
    workflow = (
        "\n".join(
            [
                "# Refund workflow",
                "",
                "1. Verify identity before order access.",
                "2. Retrieve current order and line-item state.",
                "3. Evaluate the reviewed eligibility and state constraints.",
                "4. Explain amount and original-payment destination; obtain explicit confirmation.",
                "5. Satisfy any matching approval rule before a mutation.",
                "6. Propose the covered tool mutation and report the actual tool result.",
                "7. Escalate exceptions with the minimum necessary case context.",
                *[f"- {rule.normative_text}" for rule in workflow_rules],
            ]
        )
        + "\n"
    )
    knowledge_lines = ["# Reviewed refund reference", ""]
    knowledge_lines.extend(f"- {rule.normative_text}" for rule in reference_rules)
    if not reference_rules:
        knowledge_lines.append(
            "- No reviewed knowledge or eligibility-window rule was compiled into this file."
        )
    knowledge = "\n".join(knowledge_lines) + "\n"
    guarded_keys = {(rule.stable_key, rule.revision) for rule in guarded}
    raw_policy = {
        "schema_version": "0.2",
        "default_decision": "allow",
        "scope_statement": (
            "Results apply to configured rules and tool calls routed through this "
            "policy adapter."
        ),
        "rules": [
            item
            for item in rule_records
            if (item["stable_key"], item["revision"]) in guarded_keys
        ],
    }
    raw_regression = {
        "schema_version": "0.2",
        "suite": {
            "name": "Aletheia-authored refund boundary suite",
            "version": "2",
            "data_scope": "evaluation",
            "provenance": "aletheia_authored_v1",
        },
        "tests": test_records,
    }
    try:
        policy = PolicyArtifact.model_validate(raw_policy).model_dump(
            mode="json", by_alias=True
        )
        regression = RegressionArtifact.model_validate(raw_regression).model_dump(
            mode="json", by_alias=True
        )
    except ValidationError as error:
        raise ServiceError(
            "compiler_artifact_contract_invalid",
            "A policy or regression artifact does not satisfy its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    source_map = {
        "README.md": [],
        "prompt-kernel.md": [rule.stable_key for rule in hard_rules + style_rules],
        "workflows/refunds.md": [rule.stable_key for rule in workflow_rules]
        + [rule.stable_key for rule in hard_rules],
        "knowledge/refund-reference.md": [
            rule.stable_key for rule in reference_rules
        ],
        POLICY_ARTIFACT: [rule.stable_key for rule in guarded],
        TEST_ARTIFACT: [test.stable_key for test in tests],
        TOOL_ARTIFACT: [],
        FACT_ARTIFACT: [],
        "inputs/sources.json": [],
        "inputs/rules.json": [rule.stable_key for rule in active_rules],
        "inputs/findings.json": sorted(
            {key for item in finding_records for key in item["related_rules"]}
        ),
        "source-map.json": [],
    }
    readme = "\n".join(
        [
            "# Compiled Aletheia bundle",
            "",
            "This directory is a byte-addressed, source-linked release-evaluation bundle.",
            "JSON files use canonical UTF-8 JSON (sorted keys, no insignificant whitespace) with one trailing LF.",
            "Text and YAML files are hashed as their exact UTF-8 bytes, including their final LF.",
            "`manifest.json` hashes every other emitted artifact and excludes only itself to avoid recursive self-reference.",
            "The build root is SHA-256 over the exact bytes of `manifest.json`.",
            "",
        ]
    )
    artifacts: dict[str, str] = {
        "README.md": readme,
        "prompt-kernel.md": prompt,
        "workflows/refunds.md": workflow,
        "knowledge/refund-reference.md": knowledge,
        POLICY_ARTIFACT: canonical_json_text(policy),
        TEST_ARTIFACT: _yaml_text(regression),
        TOOL_ARTIFACT: canonical_json_text(tools),
        FACT_ARTIFACT: canonical_json_text(facts),
        "inputs/sources.json": canonical_json_text(
            {"schema_version": "0.2", "sources": source_records}
        ),
        "inputs/rules.json": canonical_json_text(
            {"schema_version": "0.2", "rules": rule_records}
        ),
        "inputs/findings.json": canonical_json_text(
            {"schema_version": "0.2", "findings": finding_records}
        ),
        "source-map.json": canonical_json_text(source_map),
    }
    artifact_hashes = {
        name: artifact_hash(value) for name, value in sorted(artifacts.items())
    }
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
            "normalizer_version": item["origin"].get(
                "normalizer_version", "unspecified"
            ),
        }
        for item in source_records
    ]
    rule_inputs = [
        {
            "stable_key": item["stable_key"],
            "revision": item["revision"],
            "status": item["status"],
            "severity": item["severity"],
            "category": item["category"],
            "enforcement": item["enforcement"],
            "source_documents": sorted(
                {
                    str(ref["document_name"])
                    for ref in item["source_refs"]
                    if ref.get("document_name")
                }
            ),
            "digest": artifact_hash(item),
        }
        for item in rule_records
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
    unresolved = [
        item for item in finding_records if item["resolution_state"] == "open"
    ]
    accepted = [
        item for item in finding_records if item["resolution_state"] != "open"
    ]
    raw_input_manifest = {
        "schema_version": "0.3",
        "compiler": {
            "name": "aletheia-fixture-compiler",
            "version": COMPILER_VERSION,
            "serialization": CANONICAL_JSON_DESCRIPTION,
            "token_estimator": "char_4_estimate",
        },
        "runtime": {
            "adapter": "deterministic_replay",
            "runner_input_version": RUNNER_INPUT_VERSION,
            "policy_schema_version": policy["schema_version"],
            "domain": project.domain,
            "lifecycle": "pre_tool",
            "arms": [
                "baseline_unenforced",
                "compiled_unenforced",
                "compiled_enforced",
            ],
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
            "contains_customer_records": facts.get("contains_customer_records"),
        },
        "findings": {
            "unresolved": unresolved,
            "accepted": accepted,
        },
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
        "schema_version": "0.3",
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
            "exclusion_reason": (
                "The manifest excludes itself to avoid an impossible recursive digest."
            ),
        },
        "unresolved_findings": unresolved,
        "accepted_findings": accepted,
        "limitations": [
            EVIDENCE_LIMIT,
            (
                "Deterministic replay does not measure live-model quality, latency, "
                "tokens, or cost."
            ),
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

    stats = {
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
            "label": "char_4_estimate",
        },
        "routing": {
            "kept_in_prompt": len(hard_rules) + len(style_rules),
            "moved_to_workflow": len(workflow_rules),
            "guarded": len(guarded),
            "tested": len(tests),
        },
    }
    existing = await session.scalar(
        select(Build).where(
            Build.project_id == project_id, Build.content_hash == manifest_hash
        )
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
    await session.commit()
    await session.refresh(build)
    return build
