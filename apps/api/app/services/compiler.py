from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Build, Document, Finding, Rule, TestCase
from app.services.canonical import content_hash, token_estimate
from app.services.errors import ServiceError

COMPILER_VERSION = "0.1.0"
EVIDENCE_LIMIT = "Artifacts and results cover only reviewed rules and configured sandbox calls."


async def compile_project(session: AsyncSession, project_id: str) -> Build:
    blocking = list((await session.scalars(select(Finding).where(Finding.project_id == project_id, Finding.severity == "critical", Finding.resolution_state == "open"))).all())
    if blocking:
        raise ServiceError(
            "critical_findings_unresolved",
            "Resolve critical policy conflicts before building a candidate.",
            details={"finding_ids": [finding.id for finding in blocking], "messages": [finding.message for finding in blocking]},
            status_code=409,
        )
    documents = list((await session.scalars(select(Document).where(Document.project_id == project_id).order_by(Document.created_at))).all())
    approved = list((await session.scalars(select(Rule).where(Rule.project_id == project_id, Rule.status == "approved").order_by(Rule.stable_key, Rule.revision))).all())
    tests = list((await session.scalars(select(TestCase).where(TestCase.project_id == project_id, TestCase.review_status == "approved"))).all())
    baseline = next((doc.normalized_text for doc in documents if doc.kind == "baseline_prompt"), "")

    style_rules = [rule for rule in approved if rule.category == "style"]
    hard_rules = [rule for rule in approved if rule.category == "hard_constraint"]
    workflow_rules = [rule for rule in approved if rule.category in {"workflow", "handoff"}]
    knowledge_rules = [rule for rule in approved if rule.category == "knowledge"]
    guarded = [rule for rule in hard_rules if rule.enforcement == "guard" and rule.decidability == "machine_decidable"]

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
    workflow = "\n".join([
        "# Refund workflow",
        "",
        "1. Verify identity before order access.",
        "2. Retrieve current order and line-item state.",
        "3. Check the delivery window, returnability, and duplicate-refund state.",
        "4. Explain amount and original-payment destination; obtain explicit confirmation.",
        "5. Request a matching supervisor approval when the amount is over $200.",
        "6. Propose the covered sandbox mutation and report the actual tool result.",
        "7. Escalate exceptions with the minimum necessary case context.",
        *[f"- {rule.normative_text}" for rule in workflow_rules],
    ]) + "\n"
    knowledge = "# Refund reference\n\n- The current standard eligibility window is 30 calendar days after delivery.\n- Day 30 is eligible; day 31 is outside the standard window.\n" + "\n".join(f"- {rule.normative_text}" for rule in knowledge_rules) + "\n"
    policy = {
        "schema_version": "0.1",
        "default_decision": "allow",
        "scope_statement": "Results are limited to configured rules and covered sandbox calls.",
        "rules": [
            {
                "stable_key": rule.stable_key,
                "revision": rule.revision,
                "title": rule.title,
                "effect": rule.effect,
                "severity": rule.severity,
                "status": rule.status,
                "enforcement": rule.enforcement,
                "decidability": rule.decidability,
                "condition": rule.condition,
                "requires": rule.requires,
                "target_tools": rule.target_tools,
                "source_refs": rule.source_refs,
            }
            for rule in guarded
        ],
    }
    regression = {"schema_version": "0.1", "tests": [test.spec for test in tests]}
    source_map = {
        "prompt-kernel.md": [rule.stable_key for rule in hard_rules + style_rules],
        "workflows/refunds.md": [rule.stable_key for rule in workflow_rules] + [rule.stable_key for rule in hard_rules],
        "knowledge/refund-reference.md": [rule.stable_key for rule in knowledge_rules] + ["rule.refund.window"],
        "policies/tool-policy.json": [rule.stable_key for rule in guarded],
        "tests/regression.yaml": [test.stable_key for test in tests],
    }
    artifacts: dict[str, Any] = {
        "prompt-kernel.md": prompt,
        "workflows/refunds.md": workflow,
        "knowledge/refund-reference.md": knowledge,
        "policies/tool-policy.json": policy,
        "tests/regression.yaml": yaml.safe_dump(regression, sort_keys=False),
        "source-map.json": source_map,
    }
    input_manifest = {
        "documents": {document.name: document.original_sha256 for document in documents},
        "rules": [f"{rule.stable_key}@{rule.revision}" for rule in approved],
        "tests": [test.stable_key for test in tests],
    }
    artifact_hashes = {name: content_hash(value) for name, value in artifacts.items()}
    manifest = {
        "schema_version": "0.1",
        "compiler_version": COMPILER_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "input_hashes": input_manifest["documents"],
        "rule_revisions": input_manifest["rules"],
        "artifact_hashes": artifact_hashes,
        "test_ids": input_manifest["tests"],
        "estimator": "char_4_estimate",
        "unresolved_findings": [],
        "limitations": [EVIDENCE_LIMIT, "Fixture runs do not measure live-model quality, latency, tokens, or cost."],
    }
    artifacts["manifest.json"] = manifest
    artifacts["README.md"] = "# Compiled Aletheia bundle\n\nImmutable, source-linked artifacts for sandbox evaluation.\n"
    stats = {
        "original": {"lines": len(baseline.splitlines()), "characters": len(baseline), "tokens": token_estimate(baseline)},
        "candidate": {"lines": len(prompt.splitlines()), "characters": len(prompt), "tokens": token_estimate(prompt)},
        "reduction": {
            "lines": len(baseline.splitlines()) - len(prompt.splitlines()),
            "characters": len(baseline) - len(prompt),
            "estimated_tokens": token_estimate(baseline) - token_estimate(prompt),
            "label": "char_4_estimate",
        },
        "routing": {"kept_in_prompt": len(hard_rules) + len(style_rules), "moved_to_workflow": len(workflow_rules) + 1, "guarded": len(guarded), "tested": len(tests)},
    }
    manifest_hash = content_hash(manifest)
    existing = await session.scalar(select(Build).where(Build.content_hash == manifest_hash))
    if existing:
        return existing
    build = Build(
        project_id=project_id,
        status="succeeded",
        input_manifest=input_manifest,
        input_hash=content_hash(input_manifest),
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
