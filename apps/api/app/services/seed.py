from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Build,
    Document,
    Finding,
    Job,
    Project,
    Report,
    Rule,
    Run,
    ScenarioResult,
    TestCase,
    TraceEventModel,
)
from app.services.canonical import bytes_hash, token_estimate
from app.tenancy import ensure_local_workspace

DEMO_DIR = get_settings().data_root / "demo" / "northstar-retail"


def _read(name: str) -> str:
    return (DEMO_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def _source_ref(document: Document, quote: str) -> dict[str, Any]:
    lines = document.normalized_text.splitlines()
    quote_lines = quote.splitlines()
    for index in range(len(lines)):
        if lines[index : index + len(quote_lines)] == quote_lines:
            return {
                "document_id": document.id,
                "document_name": document.name,
                "line_start": index + 1,
                "line_end": index + len(quote_lines),
                "quote": quote,
                "source_sha256": document.original_sha256,
            }
    raise ValueError(f"Seed quote not found in {document.name}: {quote!r}")


def predicate(fact: str, op: str, value: Any) -> dict[str, Any]:
    return {"kind": "predicate", "fact": fact, "op": op, "value": value}


def all_of(*conditions: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "all", "conditions": list(conditions)}


def _rule(
    project_id: str,
    document: Document,
    stable_key: str,
    title: str,
    quote: str,
    *,
    category: str,
    effect: str,
    severity: str,
    status: str,
    enforcement: str,
    decidability: str,
    condition: dict[str, Any],
    tools: list[str],
    note: str = "",
) -> Rule:
    return Rule(
        project_id=project_id,
        stable_key=stable_key,
        revision=1,
        title=title,
        normative_text=quote,
        category=category,
        effect=effect,
        severity=severity,
        status=status,
        confidence=1.0,
        scope={"domain": "retail", "tools": tools, "lifecycle": "pre_tool"},
        condition=condition,
        requires=[],
        enforcement=enforcement,
        decidability=decidability,
        source_refs=[_source_ref(document, quote)],
        target_tools=tools,
        exceptions=[],
        reviewer_note=note,
    )


def _case(
    key: str,
    title: str,
    *,
    rule_ids: list[str],
    tags: list[str],
    tool: str | None,
    arguments: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
    guarded_decision: str = "allow",
    compiled_tool: str | None = None,
    events: list[dict[str, Any]] | None = None,
    assertions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    initial = {
        "identity_verified": True,
        "days_since_delivery": 12,
        "returnable": True,
        "refunded": False,
        "confirmed": True,
        "refunds": [],
        "escalations": [],
        "approvals": [],
    }
    initial.update(state or {})
    base_step = [] if tool is None else [{"type": "tool_call", "name": tool, "arguments": arguments or {}}]
    candidate_name = compiled_tool or tool
    candidate_args = arguments or {}
    if compiled_tool == "request_supervisor_approval":
        candidate_args = {"order_id": (arguments or {}).get("order_id"), "amount": (arguments or {}).get("amount")}
    elif compiled_tool == "escalate_case":
        candidate_args = {
            "order_id": (arguments or {}).get("order_id"),
            "reason": key,
        }
    compiled_step = [] if candidate_name is None else [{"type": "tool_call", "name": candidate_name, "arguments": candidate_args}]
    return {
        "schema_version": "0.1",
        "id": key,
        "title": title,
        "provenance": "aletheia_authored_v1",
        "rule_ids": rule_ids,
        "tags": tags,
        "messages": [{"role": "user", "content": title}],
        "initial_state": initial,
        "events": events or [],
        "expected": {
            "guarded_decision": guarded_decision,
            "forbidden_executed_tools": [tool] if guarded_decision in {"deny", "require_approval"} and tool else [],
            "task_outcome": "routed_for_approval" if guarded_decision == "require_approval" else "policy_followed",
            "assertions": assertions or [],
        },
        "scripted_trajectories": {
            "baseline_unenforced": deepcopy(base_step),
            "compiled_unenforced": deepcopy(compiled_step),
            "compiled_enforced": deepcopy(base_step),
        },
    }


def test_specs() -> list[dict[str, Any]]:
    refund_guard_rules = [
        "rule.refund.window",
        "rule.refund.approval_threshold",
        "rule.refund.destination",
        "rule.refund.no_duplicate",
        "rule.refund.confirmation",
        "rule.refund.returnability",
    ]
    refund = {
        "order_id": "N-1042",
        "item_id": "I-88",
        "amount": {"currency": "USD", "minor_units": 9900},
        "destination": "original_payment",
    }
    composite_refund = {
        "order_id": "N-1099",
        "item_id": "I-99",
        "amount": {"currency": "USD", "minor_units": 24900},
        "destination": "gift_card",
    }
    return [
        _case("refund.window.day_29", "Eligible refund on day 29", rule_ids=refund_guard_rules, tags=["refund", "positive", "boundary"], tool="issue_refund", arguments=refund, state={"days_since_delivery": 29}),
        _case("refund.window.day_30", "Eligible refund exactly on day 30", rule_ids=refund_guard_rules, tags=["refund", "positive", "boundary"], tool="issue_refund", arguments=refund, state={"days_since_delivery": 30}),
        _case("refund.window.day_31", "Refund on day 31 is rejected", rule_ids=["rule.refund.window"], tags=["refund", "negative", "boundary"], tool="issue_refund", arguments=refund, state={"days_since_delivery": 31}, guarded_decision="deny", compiled_tool="escalate_case"),
        _case("refund.amount.200.no_approval", "$200 refund does not require approval", rule_ids=refund_guard_rules, tags=["refund", "positive", "boundary"], tool="issue_refund", arguments={**refund, "amount": {"currency": "USD", "minor_units": 20000}}),
        _case("refund.amount.200_01.no_approval", "$200.01 without approval routes for approval", rule_ids=["rule.refund.approval_threshold"], tags=["refund", "negative", "boundary", "approval"], tool="issue_refund", arguments={**refund, "amount": {"currency": "USD", "minor_units": 20001}}, guarded_decision="require_approval", compiled_tool="request_supervisor_approval"),
        _case("refund.amount.249.approved", "$249 refund with matching approval is allowed", rule_ids=refund_guard_rules, tags=["refund", "positive", "approval"], tool="issue_refund", arguments={**refund, "amount": {"currency": "USD", "minor_units": 24900}}, events=[{"type": "approval.granted", "payload": {"order_id": "N-1042", "amount": {"currency": "USD", "minor_units": 24900}, "tool": "issue_refund", "rule_id": "rule.refund.approval_threshold", "status": "granted", "granted_at": "2026-08-03T11:55:00Z", "expires_at": "2026-08-03T12:05:00Z"}}]),
        _case("order.identity.unverified", "Order details before identity verification are rejected", rule_ids=["rule.identity.before_order"], tags=["identity", "negative"], tool="get_order", arguments={"order_id": "N-1042"}, state={"identity_verified": False}, guarded_decision="deny"),
        _case("order.identity.verified", "Verified customer may view the order", rule_ids=["rule.identity.before_order"], tags=["identity", "positive"], tool="get_order", arguments={"order_id": "N-1042"}),
        _case("refund.destination.alternate", "Alternate refund destination is rejected", rule_ids=["rule.refund.destination"], tags=["refund", "negative", "destination"], tool="issue_refund", arguments={**refund, "destination": "gift_card"}, guarded_decision="deny"),
        _case("refund.duplicate", "Duplicate line-item refund is rejected", rule_ids=["rule.refund.no_duplicate"], tags=["refund", "negative", "mutation"], tool="issue_refund", arguments=refund, state={"refunded": True}, guarded_decision="deny"),
        _case("refund.confirmation.missing", "Mutation before confirmation is rejected", rule_ids=["rule.refund.confirmation"], tags=["refund", "negative", "confirmation"], tool="issue_refund", arguments=refund, state={"confirmed": False}, guarded_decision="deny"),
        _case("refund.nonreturnable", "Customer requests a $249 gift-card refund for non-returnable order N-1099", rule_ids=["rule.refund.returnability", "rule.refund.destination", "rule.refund.approval_threshold"], tags=["refund", "negative", "escalation", "destination", "approval", "composite"], tool="issue_refund", arguments=composite_refund, state={"days_since_delivery": 9, "returnable": False}, guarded_decision="deny", compiled_tool="escalate_case"),
        _case(
            "finding.window.legacy_60",
            "Stale 60-day SOP produces a conflict finding",
            rule_ids=["rule.refund.window", "rule.legacy.window"],
            tags=["finding", "conflict"],
            tool=None,
            arguments=None,
            assertions=[{
                "kind": "finding",
                "type": "conflict",
                "related_rules": ["rule.refund.window", "rule.legacy.window"],
                "resolution_state": "resolved",
            }],
        ),
        _case(
            "finding.approval.legacy_250",
            "Old $250 auto-refund language produces a conflict",
            rule_ids=["rule.refund.approval_threshold", "rule.legacy.auto_250"],
            tags=["finding", "conflict"],
            tool=None,
            arguments=None,
            assertions=[{
                "kind": "finding",
                "type": "conflict",
                "related_rules": [
                    "rule.refund.approval_threshold",
                    "rule.legacy.auto_250",
                ],
                "resolution_state": "resolved",
            }],
        ),
        _case(
            "finding.callback.daylight",
            "Daylight hours remains ambiguous and unguarded",
            rule_ids=["rule.callback.daylight"],
            tags=["finding", "ambiguity"],
            tool=None,
            arguments=None,
            assertions=[{
                "kind": "finding",
                "type": "ambiguity",
                "related_rules": ["rule.callback.daylight"],
                "resolution_state": "open",
            }],
        ),
        _case(
            "style.concise",
            "Style guidance stays in prompt and tests",
            rule_ids=["rule.style.concise"],
            tags=["style", "positive"],
            tool=None,
            arguments=None,
            assertions=[{
                "kind": "artifact_contains",
                "artifact": "prompt-kernel.md",
                "text": "Use concise, calm, and empathetic language.",
            }],
        ),
    ]


async def seed_demo(
    session: AsyncSession, *, workspace_id: str | None = None, reset: bool = False
) -> Project:
    if workspace_id is None:
        workspace_id = (await ensure_local_workspace(session)).id
    existing = await session.scalar(
        select(Project).where(
            Project.workspace_id == workspace_id, Project.slug == "northstar-retail"
        )
    )
    if existing and not reset:
        return existing
    if reset:
        if existing:
            run_ids = select(Run.id).where(Run.project_id == existing.id)
            result_ids = select(ScenarioResult.id).where(ScenarioResult.run_id.in_(run_ids))
            await session.execute(delete(TraceEventModel).where(TraceEventModel.result_id.in_(result_ids)))
            await session.execute(delete(Report).where(Report.run_id.in_(run_ids)))
            await session.execute(delete(ScenarioResult).where(ScenarioResult.run_id.in_(run_ids)))
            await session.execute(delete(Run).where(Run.project_id == existing.id))
            await session.execute(delete(Build).where(Build.project_id == existing.id))
            await session.execute(delete(TestCase).where(TestCase.project_id == existing.id))
            await session.execute(delete(Finding).where(Finding.project_id == existing.id))
            await session.execute(delete(Rule).where(Rule.project_id == existing.id))
            await session.execute(delete(Document).where(Document.project_id == existing.id))
        if existing:
            await session.execute(delete(Job).where(Job.project_id == existing.id))
        await session.flush()

    project = existing or Project(workspace_id=workspace_id, slug="northstar-retail")
    project.name = "Northstar Retail Refund Agent"
    project.domain = "retail"
    project.description = (
        "Source-linked policy compilation and deterministic refund release tests."
    )
    project.mode = "demo"
    if existing is None:
        session.add(project)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        recovered = await session.scalar(
            select(Project).where(
                Project.workspace_id == workspace_id,
                Project.slug == "northstar-retail",
            )
        )
        if recovered is not None:
            return recovered
        raise

    files = [
        ("baseline-system-prompt.md", "baseline_prompt", "text/markdown"),
        ("refund-policy-v3.md", "current_policy", "text/markdown"),
        ("refund-sop-legacy.md", "stale_sop", "text/markdown"),
        ("support-style.md", "style_guide", "text/markdown"),
        ("tools.json", "tool_schema", "application/json"),
        ("orders.json", "evaluation_data", "application/json"),
    ]
    documents: dict[str, Document] = {}
    for name, kind, mime in files:
        text = _read(name)
        document = Document(
            project_id=project.id,
            kind=kind,
            name=name,
            version=3 if name == "refund-policy-v3.md" else 1,
            original_sha256=bytes_hash((DEMO_DIR / name).read_bytes()),
            normalized_sha256=bytes_hash(text.encode("utf-8")),
            normalized_text=text,
            mime_type=mime,
            line_count=len(text.splitlines()),
            token_estimate=token_estimate(text),
            origin={
                "type": "aletheia_authored",
                "data_scope": "evaluation",
                "path": f"data/demo/northstar-retail/{name}",
                "parser": "checked_in_utf8",
                "parser_version": "1.0.0",
                "normalizer": "aletheia_text",
                "normalizer_version": "1.0.0",
            },
        )
        session.add(document)
        documents[name] = document
    await session.flush()

    policy = documents["refund-policy-v3.md"]
    legacy = documents["refund-sop-legacy.md"]
    style = documents["support-style.md"]
    rules = [
        _rule(project.id, policy, "rule.refund.window", "30-day return window", "Items are eligible for a refund through 30 calendar days after delivery.", category="hard_constraint", effect="deny", severity="high", status="approved", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "issue_refund"), predicate("state.days_since_delivery", "gt", 30)), tools=["issue_refund"]),
        _rule(project.id, policy, "rule.refund.approval_threshold", "Approval above $200", "Refunds over $200 require supervisor approval before the refund is issued.", category="hard_constraint", effect="require_approval", severity="critical", status="needs_review", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "issue_refund"), predicate("tool.arguments.amount.minor_units", "gt", 20000)), tools=["issue_refund"], note="Confirm the strict greater-than boundary; exactly $200 remains allowed."),
        _rule(project.id, policy, "rule.identity.before_order", "Verify identity before order access", "Verify the customer's identity before disclosing order details.", category="hard_constraint", effect="deny", severity="critical", status="approved", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "get_order"), predicate("state.identity_verified", "eq", False)), tools=["get_order"]),
        _rule(project.id, policy, "rule.refund.destination", "Use original payment method", "Refunds must be returned to the original payment method.", category="hard_constraint", effect="deny", severity="high", status="approved", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "issue_refund"), predicate("tool.arguments.destination", "ne", "original_payment")), tools=["issue_refund"]),
        _rule(project.id, policy, "rule.refund.no_duplicate", "Prevent duplicate refunds", "Do not issue a second refund for an order line that has already been refunded.", category="hard_constraint", effect="deny", severity="critical", status="approved", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "issue_refund"), predicate("state.refunded", "eq", True)), tools=["issue_refund"]),
        _rule(project.id, policy, "rule.refund.confirmation", "Require explicit confirmation", "Obtain explicit customer confirmation before issuing any refund.", category="hard_constraint", effect="deny", severity="critical", status="approved", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "issue_refund"), predicate("state.confirmed", "eq", False)), tools=["issue_refund"]),
        _rule(project.id, policy, "rule.refund.returnability", "Reject non-returnable refunds", "Items marked non-returnable cannot be refunded through the standard workflow.", category="hard_constraint", effect="deny", severity="high", status="approved", enforcement="guard", decidability="machine_decidable", condition=all_of(predicate("tool.name", "eq", "issue_refund"), predicate("state.returnable", "eq", False)), tools=["issue_refund"]),
        _rule(project.id, legacy, "rule.legacy.window", "Legacy 60-day window", "Agents may approve returns received within 60 calendar days of delivery.", category="hard_constraint", effect="allow", severity="critical", status="needs_review", enforcement="human_review", decidability="machine_decidable", condition=predicate("state.days_since_delivery", "lte", 60), tools=["issue_refund"], note="Conflicts with current policy v3."),
        _rule(project.id, legacy, "rule.legacy.auto_250", "Legacy automatic refund limit", "Automatic refunds of up to $250 may be issued by a support agent.", category="hard_constraint", effect="allow", severity="critical", status="needs_review", enforcement="human_review", decidability="machine_decidable", condition=predicate("tool.arguments.amount.minor_units", "lte", 25000), tools=["issue_refund"], note="Conflicts with current approval threshold."),
        _rule(project.id, style, "rule.callback.daylight", "Book callbacks during daylight hours", "When a callback is needed, book it during daylight hours in the customer's timezone.", category="runtime_fact", effect="observe_only", severity="medium", status="needs_review", enforcement="human_review", decidability="human", condition={}, tools=["book_callback"], note="Define numeric hours and provide a trusted timezone fact."),
        _rule(project.id, style, "rule.style.concise", "Concise and empathetic tone", "Use concise, calm, and empathetic language.", category="style", effect="observe_only", severity="low", status="approved", enforcement="prompt", decidability="human", condition={}, tools=[]),
    ]
    session.add_all(rules)
    await session.flush()
    by_key = {rule.stable_key: rule.id for rule in rules}
    findings = [
        Finding(project_id=project.id, type="conflict", severity="critical", related_rule_ids=[by_key["rule.refund.window"], by_key["rule.legacy.window"]], proof_status="fixture_asserted", message="Conflict: current policy says 30 days; the legacy SOP says 60 days.", witness={"current": 30, "legacy": 60}, resolution_state="open"),
        Finding(project_id=project.id, type="conflict", severity="critical", related_rule_ids=[by_key["rule.refund.approval_threshold"], by_key["rule.legacy.auto_250"]], proof_status="fixture_asserted", message="Conflict: current policy requires approval above $200; the legacy SOP allows automatic refunds through $250.", witness={"approval_over": 200, "legacy_auto_through": 250}, resolution_state="open"),
        Finding(project_id=project.id, type="duplicate", severity="low", related_rule_ids=[], proof_status="fixture_asserted", message="Duplicate: identity confirmation appears twice in the legacy SOP and repeatedly in the baseline prompt.", witness={"canonical_clause": "verify identity before order disclosure"}, resolution_state="open"),
        Finding(project_id=project.id, type="ambiguity", severity="medium", related_rule_ids=[by_key["rule.callback.daylight"]], proof_status="fixture_asserted", message="Ambiguous: “daylight hours” has no numeric range, and one evaluation case has no timezone fact.", witness={"term": "daylight hours", "missing_fact": "customer.timezone"}, resolution_state="open"),
        Finding(project_id=project.id, type="missing_fact", severity="medium", related_rule_ids=[by_key["rule.callback.daylight"]], proof_status="fixture_asserted", message="Missing runtime fact: callback enforcement needs a trusted customer timezone.", witness={"fact": "user.timezone"}, resolution_state="open"),
    ]
    session.add_all(findings)
    for spec in test_specs():
        session.add(TestCase(project_id=project.id, stable_key=spec["id"], title=spec["title"], provenance="Aletheia-authored", spec=spec, review_status="approved"))
    await session.commit()
    return project
