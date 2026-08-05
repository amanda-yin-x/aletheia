from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Build, Report, Run, ScenarioResult
from app.schemas import BuildManifest, EvidencePayload, EvidenceReport
from app.services.canonical import (
    artifact_bytes,
    bytes_hash,
    canonical_json_bytes,
)
from app.services.compiler import ROOT_ARTIFACT
from app.services.errors import ServiceError

EVIDENCE_BOUNDARY = (
    "Aletheia turns agent policies into reviewed prompt, guard, and regression-test "
    "artifacts, then shows how a candidate behaves across repeatable fixture scenarios."
)
RUNTIME_BOUNDARY = (
    "Approved, machine-decidable rules can allow, block, or request approval before a "
    "covered tool call executes. Results are limited to configured rules, pinned "
    "fixtures, and calls routed through this policy adapter."
)
REPORT_DIGEST_DEFINITION = (
    "SHA-256 over canonical UTF-8 JSON bytes of this evidence object with the "
    "report_digest field omitted; canonical JSON has sorted keys, no insignificant "
    "whitespace, and one trailing LF byte. rendered_markdown is a presentation and is "
    "not part of this digest."
)


def release_gate_ready(
    metrics: dict[str, Any], dataset_manifest: dict[str, Any]
) -> bool:
    guarded = metrics.get("compiled_enforced", {})
    coverage = metrics.get("coverage", {})
    expected_cases = dataset_manifest.get("test_count")
    return (
        isinstance(expected_cases, int)
        and expected_cases > 0
        and guarded.get("cases") == expected_cases
        and coverage.get("test_count") == expected_cases
        and coverage.get("explicit_assertion_coverage") == 1
        and coverage.get("compiler_assertion_coverage") == 1
        and coverage.get("positive_negative_boundary") is True
        and coverage.get("declared_rule_linkage", {}).get("ratio") == 1
        and coverage.get("declared_source_linkage", {}).get("ratio") == 1
        and coverage.get("declared_boundary_linkage", {}).get("ratio") == 1
        and coverage.get("critical_unclassified_rules") == []
        and guarded.get("task_success_rate") == 1
        and guarded.get("executed_violation_rate") == 0
        and guarded.get("false_block_rate") == 0
        and guarded.get("tool_validation_error_rate") == 0
    )


def _manifest(build: Build) -> dict[str, Any]:
    value = build.artifacts.get(ROOT_ARTIFACT)
    try:
        manifest = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as error:
        raise ServiceError(
            "report_inputs_invalid",
            "The run's build manifest is invalid.",
            status_code=409,
        ) from error
    if (
        not isinstance(manifest, dict)
        or bytes_hash(artifact_bytes(value)) != build.content_hash
        or not isinstance(manifest.get("artifact_hashes"), dict)
        or not isinstance(manifest.get("inputs"), dict)
    ):
        raise ServiceError(
            "report_inputs_invalid",
            "The run's build root failed verification.",
            status_code=409,
        )
    try:
        return BuildManifest.model_validate(manifest).model_dump(
            mode="json", by_alias=True
        )
    except ValidationError as error:
        raise ServiceError(
            "report_inputs_invalid",
            "The run's build manifest violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error


def _stable_run_payload(
    run: Run, build: Build, results: list[ScenarioResult]
) -> dict[str, Any]:
    result_payload = [
        {
            "test": result.test_snapshot,
            "arm": result.arm,
            "verdict": result.verdict,
            "metrics": result.metrics,
            "final_state_hash": result.final_state_hash,
            "first_divergence": result.first_divergence,
        }
        for result in sorted(
            results,
            key=lambda row: (
                str(row.test_snapshot.get("stable_key", "")),
                row.arm,
            ),
        )
    ]
    return {
        "build_root_sha256": build.content_hash,
        "adapter": run.adapter,
        "model": run.model,
        "requested_arms": run.requested_arms,
        "dataset_manifest": run.dataset_manifest,
        "metrics": run.metrics,
        "results": result_payload,
    }


async def create_report(session: AsyncSession, run_id: str) -> Report:
    run = await session.get(Run, run_id)
    if not run or run.status != "succeeded":
        raise ServiceError(
            "completed_run_required",
            "A completed run is required before creating a report.",
            status_code=409,
        )
    existing = await session.scalar(select(Report).where(Report.run_id == run_id))
    if existing:
        return existing
    build = await session.get(Build, run.build_id)
    if build is None or build.project_id != run.project_id:
        raise ServiceError(
            "report_inputs_invalid",
            "The run's build does not belong to this project.",
            status_code=409,
        )
    manifest = _manifest(build)
    results = list(
        (
            await session.scalars(
                select(ScenarioResult).where(ScenarioResult.run_id == run_id)
            )
        ).all()
    )
    if any(
        not result.test_snapshot.get("stable_key")
        or not result.test_snapshot.get("title")
        for result in results
    ):
        raise ServiceError(
            "report_inputs_invalid",
            "A scenario result is missing its build-pinned test snapshot.",
            status_code=409,
        )
    failures = [
        {
            "test_id": result.test_snapshot["stable_key"],
            "title": result.test_snapshot["title"],
            "arm": result.arm,
            "first_divergence": result.first_divergence,
        }
        for result in sorted(
            results,
            key=lambda row: (
                str(row.test_snapshot.get("stable_key", "")),
                row.arm,
            ),
        )
        if result.verdict == "failed"
    ]
    verdict = (
        "Fixture suite passed"
        if release_gate_ready(run.metrics, run.dataset_manifest)
        else "Changes required"
    )
    inputs = manifest["inputs"]
    artifact_hashes = manifest["artifact_hashes"]
    run_payload = _stable_run_payload(run, build, results)
    run_digest = bytes_hash(canonical_json_bytes(run_payload))
    evidence_payload = {
        "schema_version": "0.3",
        "verdict": verdict,
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "deterministic_runtime_boundary": RUNTIME_BOUNDARY,
        "digest_definition": REPORT_DIGEST_DEFINITION,
        "provenance": {
            "dataset": run.dataset_manifest.get("name"),
            "version": run.dataset_manifest.get("version"),
            "data_scope": "Evaluation fixture — no customer records",
            "fixture_source": run.dataset_manifest.get("facts_source"),
            "contains_customer_records": run.dataset_manifest.get(
                "contains_customer_records"
            ),
            "evaluation_timestamp": run.dataset_manifest.get(
                "evaluation_timestamp"
            ),
            "test_count": run.dataset_manifest.get("test_count"),
            "dataset_manifest_sha256": run.dataset_manifest.get("hash"),
            "adapter": "Deterministic replay",
            "model": run.model or "Not used",
            "compiler_version": build.compiler_version,
            "runner_version": run.dataset_manifest.get("runner_version"),
        },
        "hashes": {
            "build_root_sha256": build.content_hash,
            "manifest_bytes_sha256": bytes_hash(
                artifact_bytes(build.artifacts[ROOT_ARTIFACT])
            ),
            "run_sha256": run_digest,
            "test_suite_sha256": run.dataset_manifest.get("tests_sha256"),
            "tool_registry_sha256": run.dataset_manifest.get("tools_sha256"),
            "fact_fixture_sha256": run.dataset_manifest.get("facts_sha256"),
            "source_documents": [
                {
                    "name": source["name"],
                    "version": source["version"],
                    "original_sha256": source["original_sha256"],
                    "normalized_sha256": source["normalized_sha256"],
                    "parser": source["parser"],
                    "parser_version": source["parser_version"],
                    "normalizer": source["normalizer"],
                    "normalizer_version": source["normalizer_version"],
                }
                for source in inputs.get("sources", [])
            ],
            "tests": [
                {
                    "stable_key": test["stable_key"],
                    "spec_sha256": test["digest"],
                }
                for test in inputs.get("tests", [])
            ],
            "artifacts": artifact_hashes,
        },
        "fixture_provenance": {
            "facts": inputs.get("facts"),
            "tools": inputs.get("tools"),
            "tests": {
                "name": run.dataset_manifest.get("name"),
                "version": run.dataset_manifest.get("version"),
                "provenance": run.dataset_manifest.get("provenance"),
                "data_scope": run.dataset_manifest.get("data_scope"),
            },
        },
        "comparison_arms": run.requested_arms,
        "test_count": run.dataset_manifest.get("test_count", 0),
        "metrics": run.metrics,
        "top_failures": failures[:8],
        "limitations": [
            "The evaluation fixture contains no customer records and does not establish market validation.",
            "Deterministic replay does not measure live-model quality, latency, tokens, or cost.",
            "Rules apply only to calls routed through the covered policy adapter.",
            "Compiler assertions prove properties of this exact build bundle, not arbitrary source corpora.",
            "This report is not a safety, security, or compliance certification.",
        ],
    }
    try:
        validated_payload = EvidencePayload.model_validate(evidence_payload).model_dump(
            mode="json", by_alias=True
        )
    except ValidationError as error:
        raise ServiceError(
            "report_contract_invalid",
            "The evaluation evidence does not satisfy its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    report_digest = bytes_hash(canonical_json_bytes(validated_payload))
    try:
        evidence = EvidenceReport.model_validate(
            {**validated_payload, "report_digest": report_digest}
        ).model_dump(mode="json", by_alias=True)
    except ValidationError as error:
        raise ServiceError(
            "report_contract_invalid",
            "The final evidence report does not satisfy its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    markdown = _markdown(evidence)
    report = Report(
        run_id=run.id,
        verdict=verdict,
        evidence=evidence,
        rendered_markdown=markdown,
        content_hash=report_digest,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


def _markdown(evidence: dict[str, Any]) -> str:
    metrics = evidence["metrics"]
    lines = [
        "# Aletheia fixture evidence",
        "",
        "## Scope and evidence boundary",
        "",
        str(evidence["evidence_boundary"]),
        "",
        str(evidence["deterministic_runtime_boundary"]),
        "",
        f"## Verdict: {evidence['verdict']}",
        "",
        (
            f"Fixture: {evidence['provenance']['dataset']} "
            f"({evidence['test_count']} cases; no customer records)."
        ),
        (
            "Adapter: deterministic replay; "
            f"model: {evidence['provenance']['model']}."
        ),
        "",
        "## Arm comparison",
        "",
        "| Arm | Task success | Executed violations | False blocks |",
        "|---|---:|---:|---:|",
    ]
    if isinstance(metrics, dict):
        for arm in evidence["comparison_arms"]:
            values = metrics.get(arm, {})
            lines.append(
                f"| {arm} | {values.get('task_success_rate', 'N/A')} | "
                f"{values.get('executed_violation_rate', 'N/A')} | "
                f"{values.get('false_block_rate', 'N/A')} |"
            )
    lines.extend(
        [
            "",
            "## Provenance hashes",
            "",
            f"- `build_root_sha256`: `{evidence['hashes']['build_root_sha256']}`",
            f"- `run_sha256`: `{evidence['hashes']['run_sha256']}`",
            f"- `test_suite_sha256`: `{evidence['hashes']['test_suite_sha256']}`",
            f"- `tool_registry_sha256`: `{evidence['hashes']['tool_registry_sha256']}`",
            f"- `fact_fixture_sha256`: `{evidence['hashes']['fact_fixture_sha256']}`",
            f"- `report_digest`: `{evidence['report_digest']}`",
            "",
            f"Digest definition: {evidence['digest_definition']}",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in evidence["limitations"])
    return "\n".join(lines) + "\n"
