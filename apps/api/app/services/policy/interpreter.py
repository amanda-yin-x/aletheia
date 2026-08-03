from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas import PolicyDecisionRequest, PolicyDecisionResult
from app.services.canonical import content_hash

MISSING = object()
ALLOWED_ROOTS = {"tool", "state", "user", "context", "events"}
ALLOWED_OPERATORS = {"eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "exists", "contains", "regex"}


@dataclass
class EvalState:
    facts: dict[str, Any]
    indeterminate: str | None = None


def resolve_fact(data: dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    if not parts or parts[0] not in ALLOWED_ROOTS:
        return MISSING
    current: Any = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return MISSING
    return current


def _ordered(left: Any, right: Any, op: str) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        raise TypeError("booleans are not ordered values")
    try:
        lnum, rnum = Decimal(str(left)), Decimal(str(right))
        return {"lt": lnum < rnum, "lte": lnum <= rnum, "gt": lnum > rnum, "gte": lnum >= rnum}[op]
    except (InvalidOperation, ValueError):
        if not isinstance(left, str) or not isinstance(right, str):
            raise TypeError("ordered comparison requires compatible numbers or strings") from None
        return {"lt": left < right, "lte": left <= right, "gt": left > right, "gte": left >= right}[op]


def evaluate_condition(node: dict[str, Any], data: dict[str, Any], state: EvalState) -> bool | None:
    kind = node.get("kind")
    if kind in {"all", "any"}:
        children = [evaluate_condition(child, data, state) for child in node.get("conditions", [])]
        if any(value is None for value in children):
            return None
        return all(children) if kind == "all" else any(children)
    if kind == "not":
        result = evaluate_condition(node.get("condition", {}), data, state)
        return None if result is None else not result
    if kind != "predicate":
        state.indeterminate = "unsupported_condition_node"
        return None

    fact, op, expected = node.get("fact", ""), node.get("op", ""), node.get("value")
    if op not in ALLOWED_OPERATORS:
        state.indeterminate = "unsupported_operator"
        return None
    actual = resolve_fact(data, fact)
    state.facts[fact] = None if actual is MISSING else actual
    if op == "exists":
        return (actual is not MISSING) is bool(expected if expected is not None else True)
    if actual is MISSING:
        state.indeterminate = f"missing_fact:{fact}"
        return None
    try:
        if op == "eq":
            return bool(actual == expected)
        if op == "ne":
            return bool(actual != expected)
        if op in {"lt", "lte", "gt", "gte"}:
            return _ordered(actual, expected, op)
        if op in {"in", "not_in"}:
            if not isinstance(expected, (list, tuple, set)):
                raise TypeError("membership comparison requires a collection")
            result = actual in expected
            return result if op == "in" else not result
        if op == "contains":
            if not isinstance(actual, (str, list, tuple, dict)):
                raise TypeError("contains requires a string or collection")
            return bool(expected in actual)
        if op == "regex":
            pattern = str(expected)
            text = str(actual)
            if len(pattern) > 128 or len(text) > 4096:
                state.indeterminate = "regex_bounds_exceeded"
                return None
            return bool(re.search(pattern, text) is not None)
    except (TypeError, ValueError, re.error) as error:
        state.indeterminate = f"invalid_comparison:{error}"
        return None
    state.indeterminate = "unknown_operator"
    return None


def _approval_matches(rule: dict[str, Any], request: PolicyDecisionRequest) -> bool:
    amount = request.tool.get("arguments", {}).get("amount")
    for event in request.events:
        if event.get("type") != "approval.granted":
            continue
        payload = event.get("payload", {})
        if payload.get("amount") == amount and payload.get("order_id") == request.tool.get("arguments", {}).get("order_id"):
            return True
    return False


def evaluate_policy(
    rules: list[dict[str, Any]], request: PolicyDecisionRequest, *, default_decision: str = "allow"
) -> PolicyDecisionResult:
    data = request.model_dump()
    matches: list[tuple[dict[str, Any], EvalState]] = []
    indeterminate_rules: list[tuple[dict[str, Any], EvalState]] = []
    for rule in rules:
        if rule.get("status") != "approved" or rule.get("enforcement") != "guard":
            continue
        targets = rule.get("target_tools", [])
        if targets and request.tool.get("name") not in targets:
            continue
        state = EvalState(facts={})
        result = evaluate_condition(rule.get("condition", {}), data, state)
        if result is True:
            matches.append((rule, state))
        elif result is None and rule.get("severity") in {"high", "critical"}:
            indeterminate_rules.append((rule, state))

    if indeterminate_rules:
        rule, state = indeterminate_rules[0]
        return _result("indeterminate", "fail_closed_unknown_fact", state.indeterminate or "Unknown fact", [rule], state.facts, request)

    for effect, code in (
        ("deny", "rule_denied"),
        ("require_prior_event", "required_event_missing"),
        ("require_approval", "approval_required"),
        ("allow", "rule_allowed"),
    ):
        selected = [(r, s) for r, s in matches if r.get("effect") == effect]
        if not selected:
            continue
        if effect == "require_approval":
            remaining = [(r, s) for r, s in selected if not _approval_matches(r, request)]
            if not remaining:
                continue
            selected = remaining
        rule_ids = [r["stable_key"] for r, _ in selected]
        facts = {key: value for _, state in selected for key, value in state.facts.items()}
        reason = {
            "deny": "A covered rule denies this tool call.",
            "require_prior_event": "A required prior event is missing.",
            "require_approval": "Matching supervisor approval is required before execution.",
            "allow": "A covered rule explicitly allows this tool call.",
        }[effect]
        return _result(effect, code, reason, [r for r, _ in selected], facts, request, rule_ids)

    return _result(default_decision, "default_allow", "No blocking rule applies.", [], {}, request)


def _result(
    decision: str,
    code: str,
    reason: str,
    rules: list[dict[str, Any]],
    facts: dict[str, Any],
    request: PolicyDecisionRequest,
    rule_ids: list[str] | None = None,
) -> PolicyDecisionResult:
    ids = rule_ids if rule_ids is not None else [rule.get("stable_key", "unknown") for rule in rules]
    payload = {"decision": decision, "reason_code": code, "rule_ids": ids, "facts": facts, "request": request.model_dump()}
    return PolicyDecisionResult(
        decision=decision,
        reason_code=code,
        reason=reason,
        rule_ids=ids,
        evaluated_facts=facts,
        decision_hash=content_hash(payload),
    )
