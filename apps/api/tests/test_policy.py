from copy import deepcopy

import pytest

from app.schemas import PolicyDecisionRequest
from app.services.policy.interpreter import EvalState, evaluate_condition, evaluate_policy
from app.services.runner import run_scenario


@pytest.mark.parametrize(
    ("op", "actual", "expected", "result"),
    [
        ("eq", "retail", "retail", True),
        ("ne", "retail", "banking", True),
        ("lt", 199.99, 200, True),
        ("lte", 200, 200, True),
        ("gt", 200.01, 200, True),
        ("gte", 200, 200, True),
        ("in", "card", ["card", "cash"], True),
        ("not_in", "crypto", ["card", "cash"], True),
        ("contains", "original_payment", "payment", True),
        ("regex", "N-1042", r"^N-\d+$", True),
    ],
)
def test_every_predicate_operator(op: str, actual: object, expected: object, result: bool) -> None:
    state = EvalState(facts={})
    node = {"kind": "predicate", "fact": "tool.arguments.value", "op": op, "value": expected}
    assert evaluate_condition(node, {"tool": {"arguments": {"value": actual}}}, state) is result


def test_nested_boolean_and_presence() -> None:
    state = EvalState(facts={})
    node = {
        "kind": "all",
        "conditions": [
            {"kind": "predicate", "fact": "state.confirmed", "op": "exists", "value": True},
            {"kind": "not", "condition": {"kind": "predicate", "fact": "state.refunded", "op": "eq", "value": True}},
            {"kind": "any", "conditions": [
                {"kind": "predicate", "fact": "state.amount", "op": "eq", "value": 200},
                {"kind": "predicate", "fact": "state.amount", "op": "eq", "value": 199},
            ]},
        ],
    }
    assert evaluate_condition(node, {"state": {"confirmed": True, "refunded": False, "amount": 200}}, state) is True


def guard(effect: str, severity: str = "critical") -> dict[str, object]:
    return {
        "stable_key": f"rule.{effect}", "status": "approved", "effect": effect,
        "severity": severity, "enforcement": "guard", "target_tools": ["issue_refund"],
        "condition": {"kind": "predicate", "fact": "tool.arguments.amount", "op": "gt", "value": 200},
    }


def test_precedence_deny_before_approval_and_allow() -> None:
    request = PolicyDecisionRequest(tool={"name": "issue_refund", "arguments": {"amount": 201}})
    result = evaluate_policy([guard("allow"), guard("require_approval"), guard("deny")], request)
    assert result.decision == "deny"
    assert result.reason_code == "rule_denied"
    assert len(result.decision_hash) == 64


def test_matching_approval_allows_by_default() -> None:
    request = PolicyDecisionRequest(
        tool={"name": "issue_refund", "arguments": {"order_id": "N-1", "amount": 249}},
        events=[{"type": "approval.granted", "payload": {"order_id": "N-1", "amount": 249}}],
    )
    result = evaluate_policy([guard("require_approval")], request)
    assert result.decision == "allow"


def test_missing_fact_fails_closed_for_high_severity() -> None:
    request = PolicyDecisionRequest(tool={"name": "issue_refund", "arguments": {}})
    result = evaluate_policy([guard("deny", "high")], request)
    assert result.decision == "indeterminate"
    assert result.reason_code == "fail_closed_unknown_fact"


def test_bounded_regex_returns_indeterminate() -> None:
    state = EvalState(facts={})
    node = {"kind": "predicate", "fact": "context.text", "op": "regex", "value": "x" * 129}
    assert evaluate_condition(node, {"context": {"text": "hello"}}, state) is None
    assert state.indeterminate == "regex_bounds_exceeded"


def test_blocked_refund_never_mutates_state() -> None:
    spec = {
        "initial_state": {"refunds": [], "refunded": False},
        "messages": [{"role": "user", "content": "refund"}],
        "events": [],
        "expected": {"guarded_decision": "require_approval", "forbidden_executed_tools": ["issue_refund"]},
        "scripted_trajectories": {"compiled_enforced": [{"type": "tool_call", "name": "issue_refund", "arguments": {"order_id": "N-1", "item_id": "I-1", "amount": 200.01, "destination": "original_payment"}}]},
    }
    initial = deepcopy(spec["initial_state"])
    events, final, metrics, _ = run_scenario(spec, "compiled_enforced", [guard("require_approval")])
    assert final == initial
    assert metrics["executed_violation"] is False
    assert any(event["type"] == "approval_required" and event["payload"]["state_mutated"] is False for event in events)
    assert not any(event["type"] == "tool_executed" for event in events)

