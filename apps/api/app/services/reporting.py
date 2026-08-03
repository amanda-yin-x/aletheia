from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Build, Report, Run, ScenarioResult, TestCase
from app.services.canonical import content_hash
from app.services.errors import ServiceError

EVIDENCE_BOUNDARY = "Aletheia turns agent policies into reviewed prompt, guard, and regression-test artifacts, then shows how a candidate behaves on repeatable sandbox scenarios."
RUNTIME_BOUNDARY = "Approved, machine-decidable rules can allow, block, or request approval before a covered sandbox tool call executes. Results are limited to the configured rules and calls passing through this adapter."


async def create_report(session: AsyncSession, run_id: str) -> Report:
    run = await session.get(Run, run_id)
    if not run or run.status != "succeeded":
        raise ServiceError("completed_run_required", "A completed run is required before creating a report.", status_code=409)
    existing = await session.scalar(select(Report).where(Report.run_id == run_id))
    if existing:
        return existing
    build = await session.get(Build, run.build_id)
    results = list((await session.scalars(select(ScenarioResult).where(ScenarioResult.run_id == run_id))).all())
    tests = {test.id: test for test in (await session.scalars(select(TestCase).where(TestCase.project_id == run.project_id))).all()}
    failures = [
        {"result_id": result.id, "test_id": tests[result.test_case_id].stable_key, "title": tests[result.test_case_id].title, "arm": result.arm, "first_divergence": result.first_divergence}
        for result in results if result.verdict == "failed"
    ]
    guarded = run.metrics.get("compiled_enforced", {})
    verdict = "Ready for sandbox pilot" if guarded.get("executed_violation_rate") == 0 and guarded.get("false_block_rate") == 0 else "Changes required"
    evidence = {
        "schema_version": "0.1",
        "verdict": verdict,
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "deterministic_runtime_boundary": RUNTIME_BOUNDARY,
        "provenance": {**run.dataset_manifest, "adapter": run.adapter, "model": run.model or "N/A — deterministic fixture"},
        "hashes": {"build": build.content_hash if build else "missing", "run": content_hash({"id": run.id, "metrics": run.metrics}), "dataset": run.dataset_manifest.get("hash", "missing")},
        "comparison_arms": run.requested_arms,
        "test_count": run.dataset_manifest.get("test_count", 0),
        "metrics": run.metrics,
        "top_failures": failures[:8],
        "limitations": [
            "Synthetic fixtures are not real customer data or market validation.",
            "The fixture adapter does not establish live-model quality, latency, tokens, or cost.",
            "Rules apply only to calls that pass through the covered sandbox adapter.",
            "This report is not a safety, security, or compliance certification.",
        ],
    }
    markdown = _markdown(evidence)
    report = Report(run_id=run.id, verdict=verdict, evidence=evidence, rendered_markdown=markdown, content_hash=content_hash(evidence))
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


def _markdown(evidence: dict[str, Any]) -> str:
    metrics = evidence["metrics"]
    lines = [
        "# Aletheia release evidence",
        "",
        "## Scope and evidence boundary",
        "",
        str(evidence["evidence_boundary"]),
        "",
        str(evidence["deterministic_runtime_boundary"]),
        "",
        f"## Verdict: {evidence['verdict']}",
        "",
        f"Dataset: Aletheia-authored synthetic refund fixtures ({evidence['test_count']} cases).",
        "Adapter: deterministic fixture; model: N/A.",
        "",
        "## Three-arm comparison",
        "",
        "| Arm | Task success | Executed violations | False blocks |",
        "|---|---:|---:|---:|",
    ]
    if isinstance(metrics, dict):
        for arm in evidence["comparison_arms"]:
            values = metrics.get(arm, {})
            lines.append(f"| {arm} | {values.get('task_success_rate', 'N/A')} | {values.get('executed_violation_rate', 'N/A')} | {values.get('false_block_rate', 'N/A')} |")
    lines.extend(["", "## Provenance hashes", ""])
    for name, value in evidence["hashes"].items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in evidence["limitations"])
    return "\n".join(lines) + "\n"
