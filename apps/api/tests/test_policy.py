from copy import deepcopy
from typing import Any

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
            {
                "kind": "not",
                "condition": {
                    "kind": "predicate",
                    "fact": "state.refunded",
                    "op": "eq",
                    "value": True,
                },
            },
            {
                "kind": "any",
                "conditions": [
                    {"kind": "predicate", "fact": "state.amount", "op": "eq", "value": 200},
                    {"kind": "predicate", "fact": "state.amount", "op": "eq", "value": 199},
                ],
            },
        ],
    }
    assert (
        evaluate_condition(
            node, {"state": {"confirmed": True, "refunded": False, "amount": 200}}, state
        )
        is True
    )


@pytest.mark.parametrize(("actual", "expected"), [(True, 1), ("201", 201)])
def test_type_invalid_equality_is_indeterminate(actual: object, expected: object) -> None:
    state = EvalState(facts={})
    node = {
        "kind": "predicate",
        "fact": "tool.arguments.value",
        "op": "eq",
        "value": expected,
    }
    assert evaluate_condition(node, {"tool": {"arguments": {"value": actual}}}, state) is None
    assert state.indeterminate and state.indeterminate.startswith("invalid_comparison:")


@pytest.mark.parametrize(
    ("kind", "known", "expected"),
    [
        ("all", False, False),
        ("all", True, None),
        ("any", True, True),
        ("any", False, None),
    ],
)
def test_three_valued_boolean_short_circuit(kind: str, known: bool, expected: bool | None) -> None:
    state = EvalState(facts={})
    node = {
        "kind": kind,
        "conditions": [
            {"kind": "predicate", "fact": "state.known", "op": "eq", "value": True},
            {"kind": "predicate", "fact": "state.missing", "op": "eq", "value": True},
        ],
    }
    assert evaluate_condition(node, {"state": {"known": known}}, state) is expected


def guard(effect: str, severity: str = "critical", **overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "stable_key": f"rule.{effect}",
        "revision": 1,
        "status": "approved",
        "effect": effect,
        "severity": severity,
        "enforcement": "guard",
        "target_tools": ["issue_refund"],
        "condition": {
            "kind": "predicate",
            "fact": "tool.arguments.amount.minor_units",
            "op": "gt",
            "value": 20000,
        },
        "requires": [],
        "exceptions": [],
    }
    rule.update(overrides)
    return rule


def test_precedence_deny_before_approval_and_allow() -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        }
    )
    result = evaluate_policy([guard("allow"), guard("require_approval"), guard("deny")], request)
    assert result.decision == "deny"
    assert result.reason_code == "rule_denied"
    assert len(result.decision_hash) == 64


def test_matching_approval_allows_by_default() -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"order_id": "N-1", "amount": {"currency": "USD", "minor_units": 24900}},
        },
        events=[
            {
                "type": "approval.granted",
                "payload": {"order_id": "N-1", "amount": {"currency": "USD", "minor_units": 24900}},
            }
        ],
    )
    result = evaluate_policy([guard("require_approval")], request)
    assert result.decision == "allow"


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ({"domain": "retail", "lifecycle": "pre_tool"}, "deny"),
        ({"domain": "banking", "lifecycle": "pre_tool"}, "allow"),
        ({"domain": "retail", "lifecycle": "post_tool"}, "allow"),
        ({"domain": "retail"}, "indeterminate"),
        ({"lifecycle": "pre_tool"}, "indeterminate"),
        ({}, "indeterminate"),
    ],
)
def test_scope_is_enforced_before_a_rule_can_match(context: dict[str, str], expected: str) -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        },
        context=context,
    )
    scope = {
        "domain": "retail",
        "tools": ["issue_refund"],
        "lifecycle": "pre_tool",
    }
    assert evaluate_policy([guard("deny", scope=scope)], request).decision == expected


def test_unknown_scope_field_fails_closed() -> None:
    rule = guard(
        "deny",
        scope={
            "domain": "retail",
            "tools": ["issue_refund"],
            "lifecycle": "pre_tool",
            "region": "ca",
        },
    )
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        },
        context={"domain": "retail"},
    )
    result = evaluate_policy([rule], request)
    assert result.decision == "indeterminate"
    assert result.reason == "unsupported_scope:region"


@pytest.mark.parametrize(
    ("effect", "expected"),
    [("not_applicable", "not_applicable"), ("allow", "allow")],
)
def test_matching_exception_controls_only_its_covered_rule(effect: str, expected: str) -> None:
    exception = {
        "condition": {
            "kind": "predicate",
            "fact": "context.customer_tier",
            "op": "eq",
            "value": "vip",
        },
        "reason": "VIP recovery exception",
        "effect": effect,
    }
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        },
        context={"customer_tier": "vip"},
    )
    result = evaluate_policy([guard("deny", exceptions=[exception])], request)
    assert result.decision == expected
    assert result.rule_ids == ["rule.deny"]


def test_nonmatching_exception_does_not_weaken_rule() -> None:
    exception = {
        "condition": {
            "kind": "predicate",
            "fact": "context.customer_tier",
            "op": "eq",
            "value": "vip",
        },
        "reason": "VIP recovery exception",
    }
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        },
        context={"customer_tier": "standard"},
    )
    result = evaluate_policy([guard("deny", exceptions=[exception])], request)
    assert result.decision == "deny"


def test_not_applicable_exception_never_bypasses_fail_closed_default() -> None:
    exception = {
        "condition": {
            "kind": "predicate",
            "fact": "context.customer_tier",
            "op": "eq",
            "value": "vip",
        },
        "reason": "VIP recovery exception",
    }
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        },
        context={"customer_tier": "vip"},
    )
    result = evaluate_policy(
        [guard("deny", exceptions=[exception])], request, default_decision="deny"
    )
    assert result.decision == "deny"
    assert result.reason_code == "default_deny"


def test_unknown_exception_condition_fails_closed() -> None:
    exception = {
        "condition": {
            "kind": "predicate",
            "fact": "context.customer_tier",
            "op": "eq",
            "value": "vip",
        },
        "reason": "VIP recovery exception",
    }
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        }
    )
    result = evaluate_policy([guard("deny", exceptions=[exception])], request)
    assert result.decision == "indeterminate"
    assert result.reason == "missing_fact:context.customer_tier"


def prior_event_rule() -> dict[str, Any]:
    return guard(
        "require_prior_event",
        requires=[
            {
                "kind": "prior_event",
                "event_type": "identity.verified",
                "match_arguments": ["order_id"],
            }
        ],
    )


@pytest.mark.parametrize(
    "events",
    [
        [],
        [{"type": "identity.verified", "payload": {"order_id": "N-2"}}],
        [{"type": "other.event", "payload": {"order_id": "N-1"}}],
    ],
)
def test_prior_event_requirement_needs_matching_type_and_correlation(
    events: list[dict[str, Any]],
) -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {
                "order_id": "N-1",
                "amount": {"currency": "USD", "minor_units": 20100},
            },
        },
        events=events,
    )
    result = evaluate_policy([prior_event_rule()], request)
    assert result.decision == "require_prior_event"
    assert result.reason_code == "required_event_missing"


def test_satisfied_prior_event_requirement_removes_the_block() -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {
                "order_id": "N-1",
                "amount": {"currency": "USD", "minor_units": 20100},
            },
        },
        events=[{"type": "identity.verified", "payload": {"order_id": "N-1"}}],
    )
    result = evaluate_policy([prior_event_rule()], request)
    assert result.decision == "allow"
    assert result.reason_code == "default_allow"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"identity_verified": True}, "deny"),
        ({"identity_verified": False}, "require_prior_event"),
        ({}, "indeterminate"),
    ],
)
def test_fact_prerequisite_must_be_proven(state: dict[str, Any], expected: str) -> None:
    rule = guard(
        "deny",
        requires=[
            {
                "kind": "fact",
                "fact": "state.identity_verified",
                "op": "eq",
                "value": True,
            }
        ],
    )
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 20100}},
        },
        state=state,
    )
    assert evaluate_policy([rule], request).decision == expected


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "requires": [
                {
                    "kind": "prior_event",
                    "event_type": "identity.verified",
                    "match_arguments": "order_id",
                }
            ]
        },
        {
            "exceptions": [
                {
                    "condition": {
                        "kind": "predicate",
                        "fact": "context.customer_tier",
                        "op": "eq",
                        "value": "vip",
                    },
                    "effect": "allow",
                }
            ]
        },
    ],
)
def test_malformed_requirement_or_exception_fails_closed(
    overrides: dict[str, Any],
) -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {
                "order_id": "N-1",
                "amount": {"currency": "USD", "minor_units": 20100},
            },
        },
        context={"customer_tier": "vip"},
    )
    result = evaluate_policy([guard("deny", **overrides)], request)
    assert result.decision == "indeterminate"


@pytest.mark.parametrize(
    "payload_override",
    [
        {"tool": "cancel_item"},
        {"rule_id": "rule.some_other_rule"},
        {"rule_revision": 2},
        {"expired": True},
        {"revoked": True},
        {"consumed": True},
        {"status": "revoked"},
        {"expires_at": "2026-08-03T11:59:59Z"},
        {"valid_from": "2026-08-03T12:00:01Z"},
    ],
)
def test_wrong_or_inactive_approval_never_authorizes(
    payload_override: dict[str, Any],
) -> None:
    amount = {"currency": "USD", "minor_units": 24900}
    payload = {"order_id": "N-1", "amount": amount, **payload_override}
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"order_id": "N-1", "amount": amount},
        },
        context={"now": "2026-08-03T12:00:00Z"},
        events=[{"type": "approval.granted", "payload": payload}],
    )
    result = evaluate_policy([guard("require_approval")], request)
    assert result.decision == "require_approval"
    assert result.reason_code == "approval_required"


def test_tool_rule_and_expiry_bound_approval_authorizes() -> None:
    amount = {"currency": "USD", "minor_units": 24900}
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"order_id": "N-1", "amount": amount},
        },
        context={"now": "2026-08-03T12:00:00Z"},
        events=[
            {
                "type": "approval.granted",
                "payload": {
                    "order_id": "N-1",
                    "amount": amount,
                    "tool": "issue_refund",
                    "rule_id": "rule.require_approval",
                    "rule_revision": 1,
                    "status": "granted",
                    "expires_at": "2026-08-03T12:05:00Z",
                },
            }
        ],
    )
    assert evaluate_policy([guard("require_approval")], request).decision == "allow"


def test_explicit_approval_requirement_uses_declared_event_and_arguments() -> None:
    rule = guard(
        "require_approval",
        requires=[
            {
                "kind": "approval",
                "event_type": "supervisor.approved",
                "match_arguments": ["order_id"],
            }
        ],
    )
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {
                "order_id": "N-1",
                "amount": {"currency": "USD", "minor_units": 24900},
            },
        },
        events=[
            {
                "type": "supervisor.approved",
                "payload": {
                    "order_id": "N-1",
                    "tool": "issue_refund",
                    "rule_id": "rule.require_approval",
                },
            }
        ],
    )
    assert evaluate_policy([rule], request).decision == "allow"


@pytest.mark.parametrize(
    ("identity", "expected"),
    [
        ({"rule_revision": 1}, "require_approval"),
        ({"tool": "issue_refund"}, "require_approval"),
        (
            {"tool": "issue_refund", "rule_id": "rule.require_approval"},
            "allow",
        ),
    ],
)
def test_uncorrelated_approval_requires_tool_and_rule_identity(
    identity: dict[str, Any], expected: str
) -> None:
    rule = guard(
        "require_approval",
        requires=[
            {
                "kind": "approval",
                "event_type": "supervisor.approved",
                "match_arguments": [],
            }
        ],
    )
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {"amount": {"currency": "USD", "minor_units": 24900}},
        },
        events=[{"type": "supervisor.approved", "payload": identity}],
    )
    assert evaluate_policy([rule], request).decision == expected


def test_precedence_is_deny_unknown_prior_approval_allow() -> None:
    request = PolicyDecisionRequest(
        tool={
            "name": "issue_refund",
            "arguments": {
                "order_id": "N-1",
                "amount": {"currency": "USD", "minor_units": 20100},
            },
        }
    )
    unknown = guard(
        "allow",
        stable_key="rule.unknown",
        condition={
            "kind": "predicate",
            "fact": "state.unavailable",
            "op": "eq",
            "value": True,
        },
    )
    prior = guard("require_prior_event")
    approval = guard("require_approval")
    allow = guard("allow")

    assert evaluate_policy([unknown, guard("deny")], request).decision == "deny"
    assert evaluate_policy([unknown, allow], request).decision == "indeterminate"
    assert evaluate_policy([prior, approval, allow], request).decision == "require_prior_event"
    assert evaluate_policy([approval, allow], request).decision == "require_approval"


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


def test_regex_uses_re2_and_rejects_backreferences() -> None:
    state = EvalState(facts={})
    node = {
        "kind": "predicate",
        "fact": "context.text",
        "op": "regex",
        "value": r"^(a+)\1$",
    }
    assert evaluate_condition(node, {"context": {"text": "aaaa"}}, state) is None
    assert state.indeterminate and state.indeterminate.startswith("invalid_comparison:")


def test_blocked_refund_never_mutates_state() -> None:
    spec = {
        "initial_state": {"refunds": [], "refunded": False},
        "messages": [{"role": "user", "content": "refund"}],
        "events": [],
        "expected": {
            "guarded_decision": "require_approval",
            "forbidden_executed_tools": ["issue_refund"],
        },
        "scripted_trajectories": {
            "compiled_enforced": [
                {
                    "type": "tool_call",
                    "name": "issue_refund",
                    "arguments": {
                        "order_id": "N-1",
                        "item_id": "I-1",
                        "amount": {"currency": "USD", "minor_units": 20001},
                        "destination": "original_payment",
                    },
                }
            ]
        },
    }
    initial = deepcopy(spec["initial_state"])
    events, final, metrics, _ = run_scenario(spec, "compiled_enforced", [guard("require_approval")])
    assert final == initial
    assert metrics["executed_violation"] is False
    assert any(
        event["type"] == "approval_required" and event["payload"]["state_mutated"] is False
        for event in events
    )
    assert not any(event["type"] == "tool_executed" for event in events)
