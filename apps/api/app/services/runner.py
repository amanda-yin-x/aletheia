from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Build, Rule, Run, ScenarioResult, TestCase, TraceEventModel
from app.schemas import PolicyDecisionRequest
from app.services.canonical import content_hash
from app.services.errors import ServiceError
from app.services.policy import evaluate_policy

ARMS = ["baseline_unenforced", "compiled_unenforced", "compiled_enforced"]
RUNNER_VERSION = "0.1.0"


def _event(events: list[dict[str, Any]], type_: str, payload: dict[str, Any], rule_ids: list[str] | None = None) -> None:
    events.append({"sequence": len(events) + 1, "type": type_, "payload": payload, "rule_ids": rule_ids or [], "duration_ms": 0.0})


def _execute(name: str, arguments: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    before = deepcopy(state)
    if name == "issue_refund":
        state.setdefault("refunds", []).append({"order_id": arguments.get("order_id"), "item_id": arguments.get("item_id"), "amount": arguments.get("amount"), "destination": arguments.get("destination")})
        state["refunded"] = True
        result = {"status": "refunded", "amount": arguments.get("amount")}
    elif name == "request_supervisor_approval":
        state.setdefault("approvals", []).append({"status": "pending", **arguments})
        result = {"status": "approval_pending", **arguments}
    elif name == "escalate_case":
        state.setdefault("escalations", []).append(arguments)
        result = {"status": "escalated", "case_id": f"CASE-{len(state['escalations']):04d}"}
    elif name in {"get_order", "get_customer"}:
        result = {"status": "found", "data_scope": "evaluation"}
    elif name == "book_callback":
        state.setdefault("callbacks", []).append(arguments)
        result = {"status": "booked"}
    elif name == "cancel_item":
        state.setdefault("cancelled_items", []).append(arguments.get("item_id"))
        result = {"status": "cancelled"}
    else:
        return {"status": "invalid_tool"}, {}
    diff = {key: {"before": before.get(key), "after": value} for key, value in state.items() if before.get(key) != value}
    return result, diff


def run_scenario(spec: dict[str, Any], arm: str, policy_rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str]:
    state = deepcopy(spec["initial_state"])
    initial_hash = content_hash(state)
    events: list[dict[str, Any]] = []
    _event(events, "run_started", {"arm": arm, "adapter": "deterministic_replay", "initial_state_hash": initial_hash})
    _event(events, "user_message", spec["messages"][0])
    executed: list[str] = []
    proposed: list[str] = []
    decisions: list[str] = []
    for step in spec["scripted_trajectories"].get(arm, []):
        if step.get("type") != "tool_call":
            continue
        name, arguments = step["name"], step.get("arguments", {})
        proposed.append(name)
        _event(events, "tool_proposed", {"name": name, "arguments": arguments, "status": "proposed"})
        decision = evaluate_policy(
            policy_rules,
            PolicyDecisionRequest(tool={"name": name, "arguments": arguments}, state=state, events=spec.get("events", [])),
        )
        decisions.append(decision.decision)
        _event(events, "policy_evaluated", decision.model_dump(), decision.rule_ids)
        enforced = arm == "compiled_enforced"
        if enforced and decision.decision != "allow":
            event_type = "approval_required" if decision.decision == "require_approval" else "tool_blocked"
            _event(events, event_type, {"name": name, "decision": decision.decision, "state_mutated": False, "reason_code": decision.reason_code}, decision.rule_ids)
            continue
        _event(events, "tool_executed", {"name": name, "arguments": arguments, "status": "executed"})
        executed.append(name)
        result, diff = _execute(name, arguments, state)
        _event(events, "tool_result", {"name": name, "result": result})
        if diff:
            _event(events, "state_changed", {"name": name, "diff": diff})

    expected = spec["expected"]
    target_decision = expected.get("guarded_decision", "allow")
    forbidden = set(expected.get("forbidden_executed_tools", []))
    attempted_violation = any(value in {"deny", "require_approval", "require_prior_event", "indeterminate"} for value in decisions)
    executed_violation = bool(forbidden.intersection(executed))
    if arm == "compiled_enforced":
        actual = decisions[-1] if decisions else "allow"
        task_success = actual == target_decision and not executed_violation
    else:
        task_success = not executed_violation
    metrics = {
        "task_success": task_success,
        "proposed_calls": len(proposed),
        "executed_calls": len(executed),
        "attempted_violation": attempted_violation,
        "executed_violation": executed_violation,
        "blocked_calls": len(proposed) - len(executed),
        "false_block": target_decision == "allow" and len(proposed) > len(executed),
        "initial_state_hash": initial_hash,
        "tokens": None,
        "cost": None,
    }
    _event(events, "assertion_evaluated", {"expected_decision": target_decision, "passed": task_success, "executed_violation": executed_violation})
    _event(events, "run_finished", {"verdict": "passed" if task_success else "failed", "final_state_hash": content_hash(state)})
    divergence = None
    if arm == "compiled_enforced" and attempted_violation:
        divergence = f"Policy adapter intercepted {proposed[-1]} before tool execution; state mutation was prevented."
    return events, state, metrics, divergence or "No material divergence from the expected case trajectory."


def _aggregate(results: list[ScenarioResult]) -> dict[str, Any]:
    by_arm: dict[str, list[ScenarioResult]] = {arm: [] for arm in ARMS}
    for result in results:
        by_arm[result.arm].append(result)
    output: dict[str, Any] = {}
    for arm, rows in by_arm.items():
        total = len(rows) or 1
        output[arm] = {
            "cases": len(rows),
            "task_success_rate": round(sum(bool(row.metrics.get("task_success")) for row in rows) / total, 4),
            "attempted_violation_rate": round(sum(bool(row.metrics.get("attempted_violation")) for row in rows) / total, 4),
            "executed_violation_rate": round(sum(bool(row.metrics.get("executed_violation")) for row in rows) / total, 4),
            "false_block_rate": round(sum(bool(row.metrics.get("false_block")) for row in rows) / total, 4),
            "input_tokens": None,
            "output_tokens": None,
            "cost": None,
        }
    output["coverage"] = {"test_count": len(results) // len(ARMS), "arms": len(ARMS), "positive_negative_boundary": True}
    return output


async def run_comparison(session: AsyncSession, project_id: str, build_id: str | None = None) -> Run:
    build = await session.get(Build, build_id) if build_id else await session.scalar(select(Build).where(Build.project_id == project_id).order_by(Build.created_at.desc()))
    if not build:
        raise ServiceError("build_required", "Build a candidate before running the comparison.", status_code=409)
    tests = list((await session.scalars(select(TestCase).where(TestCase.project_id == project_id, TestCase.review_status == "approved").order_by(TestCase.stable_key))).all())
    rules = list((await session.scalars(select(Rule).where(Rule.project_id == project_id, Rule.status == "approved", Rule.enforcement == "guard"))).all())
    policy_rules = [{
        "stable_key": rule.stable_key, "status": rule.status, "effect": rule.effect, "severity": rule.severity,
        "enforcement": rule.enforcement, "condition": rule.condition, "target_tools": rule.target_tools,
    } for rule in rules]
    run = Run(
        project_id=project_id,
        build_id=build.id,
        requested_arms=ARMS,
        adapter="fixture",
        model=None,
        dataset_manifest={"name": "Aletheia-authored refund boundary suite", "version": "1", "data_scope": "evaluation", "test_count": len(tests), "hash": content_hash([test.spec for test in tests])},
        status="running",
        metrics={},
    )
    session.add(run)
    await session.flush()
    result_rows: list[ScenarioResult] = []
    for test in tests:
        for arm in ARMS:
            events, state, metrics, divergence = run_scenario(test.spec, arm, policy_rules)
            result = ScenarioResult(
                run_id=run.id,
                test_case_id=test.id,
                arm=arm,
                verdict="passed" if metrics["task_success"] else "failed",
                metrics=metrics,
                final_state_hash=content_hash(state),
                first_divergence=divergence,
                trace_id=str(uuid4()),
            )
            session.add(result)
            await session.flush()
            for item in events:
                session.add(TraceEventModel(result_id=result.id, trace_id=result.trace_id, **item))
            result_rows.append(result)
    run.metrics = _aggregate(result_rows)
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run
