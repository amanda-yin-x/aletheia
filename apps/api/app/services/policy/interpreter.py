from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import re2  # type: ignore[import-untyped]

from app.schemas import PolicyDecisionRequest, PolicyDecisionResult
from app.services.canonical import content_hash

MISSING = object()
ALLOWED_ROOTS = {"tool", "state", "user", "context", "events"}
ALLOWED_OPERATORS = {
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "in",
    "not_in",
    "exists",
    "contains",
    "regex",
}
SUPPORTED_SCOPE_KEYS = {"domain", "tools", "lifecycle"}
SUPPORTED_EFFECTS = {"allow", "deny", "require_approval", "require_prior_event"}
BLOCKING_SEVERITIES = {"high", "critical"}
Decision = Literal[
    "allow",
    "deny",
    "require_approval",
    "require_prior_event",
    "indeterminate",
    "not_applicable",
]


@dataclass
class EvalState:
    facts: dict[str, Any]
    indeterminate: str | None = None


def _mark_indeterminate(state: EvalState, reason: str) -> None:
    if state.indeterminate is None:
        state.indeterminate = reason


def resolve_fact(data: dict[str, Any], path: str) -> Any:
    if not isinstance(path, str):
        return MISSING
    parts = path.split(".")
    if not parts or parts[0] not in ALLOWED_ROOTS or any(not part for part in parts):
        return MISSING
    current: Any = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return MISSING
    return current


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _decimal(value: Any) -> Decimal:
    number = Decimal(str(value))
    if not number.is_finite():
        raise TypeError("numeric comparison requires finite values")
    return number


def _values_equal(left: Any, right: Any) -> bool:
    if _is_number(left) and _is_number(right):
        return _decimal(left) == _decimal(right)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return bool(left == right)


def _event_values_equal(left: Any, right: Any) -> bool:
    try:
        return _values_equal(left, right)
    except (InvalidOperation, TypeError, ValueError):
        return False


def _predicate_values_equal(left: Any, right: Any) -> bool:
    if not (_is_number(left) and _is_number(right)) and type(left) is not type(right):
        raise TypeError("equality comparison requires values of the same type")
    return _values_equal(left, right)


def _ordered(left: Any, right: Any, op: str) -> bool:
    if _is_number(left) and _is_number(right):
        lvalue, rvalue = _decimal(left), _decimal(right)
        return {
            "lt": lvalue < rvalue,
            "lte": lvalue <= rvalue,
            "gt": lvalue > rvalue,
            "gte": lvalue >= rvalue,
        }[op]
    if isinstance(left, str) and isinstance(right, str):
        return {
            "lt": left < right,
            "lte": left <= right,
            "gt": left > right,
            "gte": left >= right,
        }[op]
    raise TypeError("ordered comparison requires numbers or strings of the same type")


def evaluate_condition(node: dict[str, Any], data: dict[str, Any], state: EvalState) -> bool | None:
    if not isinstance(node, dict):
        _mark_indeterminate(state, "invalid_condition_node")
        return None

    kind = node.get("kind")
    if kind in {"all", "any"}:
        raw_children = node.get("conditions")
        if not isinstance(raw_children, list) or not raw_children:
            _mark_indeterminate(state, "invalid_boolean_condition")
            return None
        children = [evaluate_condition(child, data, state) for child in raw_children]
        if kind == "all":
            if False in children:
                return False
            return None if None in children else True
        if True in children:
            return True
        return None if None in children else False
    if kind == "not":
        child = node.get("condition")
        if not isinstance(child, dict):
            _mark_indeterminate(state, "invalid_not_condition")
            return None
        result = evaluate_condition(child, data, state)
        return None if result is None else not result
    if kind != "predicate":
        _mark_indeterminate(state, "unsupported_condition_node")
        return None

    fact, op, expected = node.get("fact"), node.get("op"), node.get("value")
    if not isinstance(fact, str) or not fact:
        _mark_indeterminate(state, "invalid_fact_path")
        return None
    if op not in ALLOWED_OPERATORS:
        _mark_indeterminate(state, "unsupported_operator")
        return None
    actual = resolve_fact(data, fact)
    state.facts[fact] = None if actual is MISSING else actual
    if op == "exists":
        if expected is None:
            expected = True
        if not isinstance(expected, bool):
            _mark_indeterminate(state, "invalid_comparison:exists requires a boolean")
            return None
        return (actual is not MISSING) is expected
    if actual is MISSING:
        _mark_indeterminate(state, f"missing_fact:{fact}")
        return None
    try:
        if op == "eq":
            return _predicate_values_equal(actual, expected)
        if op == "ne":
            return not _predicate_values_equal(actual, expected)
        if op in {"lt", "lte", "gt", "gte"}:
            return _ordered(actual, expected, op)
        if op in {"in", "not_in"}:
            if not isinstance(expected, (list, tuple, set)):
                raise TypeError("membership comparison requires a collection")
            result = any(_values_equal(actual, candidate) for candidate in expected)
            return result if op == "in" else not result
        if op == "contains":
            if isinstance(actual, str):
                if not isinstance(expected, str):
                    raise TypeError("string contains requires a string value")
                return expected in actual
            if isinstance(actual, (list, tuple)):
                return any(_values_equal(candidate, expected) for candidate in actual)
            if isinstance(actual, dict):
                return any(_values_equal(candidate, expected) for candidate in actual)
            raise TypeError("contains requires a string or collection")
        if op == "regex":
            if not isinstance(expected, str) or not isinstance(actual, str):
                raise TypeError("regex requires string pattern and fact values")
            if len(expected) > 128 or len(actual) > 4096:
                _mark_indeterminate(state, "regex_bounds_exceeded")
                return None
            return bool(re2.search(expected, actual) is not None)
    except (InvalidOperation, TypeError, ValueError, re2.error) as error:
        _mark_indeterminate(state, f"invalid_comparison:{error}")
        return None
    _mark_indeterminate(state, "unknown_operator")
    return None


def _three_valued_all(results: list[bool | None]) -> bool | None:
    if False in results:
        return False
    return None if None in results else True


def _scope_value_matches(actual: Any, expected: Any, state: EvalState, fact: str) -> bool | None:
    state.facts[fact] = actual
    if not isinstance(expected, str) or not expected:
        _mark_indeterminate(state, f"invalid_scope:{fact.removeprefix('context.')}")
        return None
    if not isinstance(actual, str):
        _mark_indeterminate(state, f"invalid_fact_type:{fact}")
        return None
    return actual == expected


def _scope_matches(
    rule: dict[str, Any], request: PolicyDecisionRequest, state: EvalState
) -> bool | None:
    scope = rule.get("scope", {})
    if not isinstance(scope, dict):
        _mark_indeterminate(state, "invalid_scope")
        return None
    if not scope:
        return True

    results: list[bool | None] = []
    unknown_keys = set(scope) - SUPPORTED_SCOPE_KEYS
    if unknown_keys:
        _mark_indeterminate(state, f"unsupported_scope:{sorted(unknown_keys)[0]}")
        results.append(None)
    missing_keys = SUPPORTED_SCOPE_KEYS - set(scope)
    if missing_keys:
        _mark_indeterminate(state, f"missing_scope_field:{sorted(missing_keys)[0]}")
        results.append(None)

    if "tools" in scope:
        tools = scope["tools"]
        if not isinstance(tools, list) or not all(isinstance(tool, str) and tool for tool in tools):
            _mark_indeterminate(state, "invalid_scope:tools")
            results.append(None)
        else:
            state.facts["tool.name"] = request.tool.name
            results.append(not tools or request.tool.name in tools)

    if "domain" in scope:
        domain = request.context.get("domain", MISSING)
        if domain is MISSING:
            state.facts["context.domain"] = None
            _mark_indeterminate(state, "missing_fact:context.domain")
            results.append(None)
        else:
            results.append(_scope_value_matches(domain, scope["domain"], state, "context.domain"))

    if "lifecycle" in scope:
        lifecycle = request.context.get("lifecycle", MISSING)
        if lifecycle is MISSING:
            state.facts["context.lifecycle"] = None
            _mark_indeterminate(state, "missing_fact:context.lifecycle")
            results.append(None)
        else:
            results.append(
                _scope_value_matches(lifecycle, scope["lifecycle"], state, "context.lifecycle")
            )

    return _three_valued_all(results)


def _exception_applies(
    rule: dict[str, Any], data: dict[str, Any], state: EvalState
) -> tuple[bool | None, Literal["allow", "not_applicable"] | None]:
    exceptions = rule.get("exceptions", [])
    if not isinstance(exceptions, list):
        _mark_indeterminate(state, "invalid_exceptions")
        return None, None

    saw_unknown = False
    matched_effects: list[Literal["allow", "not_applicable"]] = []
    for entry in exceptions:
        if not isinstance(entry, dict):
            _mark_indeterminate(state, "invalid_exception")
            saw_unknown = True
            continue
        unknown_keys = set(entry) - {"condition", "reason", "effect"}
        condition = entry.get("condition")
        reason = entry.get("reason")
        effect = entry.get("effect", "not_applicable")
        if (
            unknown_keys
            or not isinstance(condition, dict)
            or not isinstance(reason, str)
            or not reason
            or effect not in {"allow", "not_applicable"}
        ):
            _mark_indeterminate(state, "invalid_exception")
            saw_unknown = True
            continue
        result = evaluate_condition(condition, data, state)
        if result is True:
            matched_effects.append(effect)
        elif result is None:
            saw_unknown = True
    if matched_effects:
        return True, "allow" if "allow" in matched_effects else "not_applicable"
    return (None, None) if saw_unknown else (False, None)


def _resolve_payload(payload: dict[str, Any], path: str) -> Any:
    if not isinstance(path, str) or not path:
        return MISSING
    current: Any = payload
    for part in path.split("."):
        if not part or not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _correlation_pairs(
    raw_fields: Any, state: EvalState, *, label: str
) -> list[tuple[str, str]] | None:
    if isinstance(raw_fields, list) and all(
        isinstance(field, str) and field for field in raw_fields
    ):
        return [(f"tool.arguments.{field}", field) for field in raw_fields]
    _mark_indeterminate(state, f"invalid_{label}_correlation_fields")
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _approval_rule_identity(rule: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    for key in ("id", "stable_key"):
        value = rule.get(key)
        if isinstance(value, str) and value:
            identities.add(value)
    stable_key = rule.get("stable_key")
    revision = rule.get("revision")
    if (
        isinstance(stable_key, str)
        and stable_key
        and isinstance(revision, int)
        and not isinstance(revision, bool)
    ):
        identities.update({f"{stable_key}@{revision}", f"{stable_key}:{revision}"})
    return identities


def _approval_event_is_valid(
    payload: dict[str, Any],
    rule: dict[str, Any],
    request: PolicyDecisionRequest,
    state: EvalState,
    *,
    require_bound_identity: bool,
) -> bool:
    for flag in ("expired", "revoked", "consumed"):
        if flag in payload and (not isinstance(payload[flag], bool) or payload[flag]):
            return False
    if "status" in payload:
        status = payload["status"]
        if not isinstance(status, str) or status not in {"active", "approved", "granted"}:
            return False

    tool_keys = [key for key in ("tool", "tool_name") if key in payload]
    if any(
        not isinstance(payload[key], str) or payload[key] != request.tool.name for key in tool_keys
    ):
        return False

    identities = _approval_rule_identity(rule)
    rule_keys = [key for key in ("rule", "rule_id", "rule_stable_key") if key in payload]
    if any(
        not isinstance(payload[key], str) or payload[key] not in identities for key in rule_keys
    ):
        return False
    has_rule_revision = "rule_revision" in payload
    if has_rule_revision:
        if not isinstance(payload["rule_revision"], int) or isinstance(
            payload["rule_revision"], bool
        ):
            return False
        if payload["rule_revision"] != rule.get("revision"):
            return False

    if require_bound_identity and (not tool_keys or not rule_keys):
        return False

    temporal_keys = [
        key for key in ("expires_at", "valid_until", "valid_from", "not_before") if key in payload
    ]
    if temporal_keys:
        now = _parse_timestamp(request.context.get("now"))
        state.facts["context.now"] = request.context.get("now")
        if now is None:
            return False
        for key in ("expires_at", "valid_until"):
            if key in payload:
                expires_at = _parse_timestamp(payload[key])
                if expires_at is None or now >= expires_at:
                    return False
        for key in ("valid_from", "not_before"):
            if key in payload:
                valid_from = _parse_timestamp(payload[key])
                if valid_from is None or now < valid_from:
                    return False
    return True


def _event_requirement_matches(
    requirement: dict[str, Any],
    rule: dict[str, Any],
    request: PolicyDecisionRequest,
    data: dict[str, Any],
    state: EvalState,
    *,
    allow_legacy_approval: bool = False,
) -> bool | None:
    kind = requirement.get("kind")
    supported = {"kind", "event_type", "fact", "op", "value", "match_arguments"}
    unknown_keys = set(requirement) - supported
    if unknown_keys:
        _mark_indeterminate(state, f"unsupported_requirement_field:{sorted(unknown_keys)[0]}")
        return None
    if kind not in {"prior_event", "approval"}:
        _mark_indeterminate(state, "invalid_event_requirement_kind")
        return None
    if (
        requirement.get("fact") is not None
        or requirement.get("op") is not None
        or requirement.get("value") is not None
    ):
        _mark_indeterminate(state, "invalid_event_requirement_fields")
        return None

    event_type = requirement.get("event_type")
    match_arguments = requirement.get("match_arguments", [])
    if not isinstance(event_type, str) or not event_type:
        _mark_indeterminate(state, "invalid_requirement_event_type")
        return None
    if not isinstance(match_arguments, list) or not all(
        isinstance(argument, str) and argument for argument in match_arguments
    ):
        _mark_indeterminate(state, "invalid_requirement_match_arguments")
        return None

    correlations = _correlation_pairs(match_arguments, state, label=kind)
    if correlations is None:
        return None
    request_values: list[tuple[str, str, Any]] = []
    for request_path, event_path in correlations:
        actual = resolve_fact(data, request_path)
        state.facts[request_path] = None if actual is MISSING else actual
        if actual is MISSING:
            _mark_indeterminate(state, f"missing_fact:{request_path}")
            return None
        request_values.append((request_path, event_path, actual))

    matching_type_count = 0
    for event in request.events:
        if event.type != event_type:
            continue
        matching_type_count += 1
        if kind == "approval" and not _approval_event_is_valid(
            event.payload,
            rule,
            request,
            state,
            require_bound_identity=not allow_legacy_approval,
        ):
            continue
        if any(
            (event_value := _resolve_payload(event.payload, event_path)) is MISSING
            or not _event_values_equal(actual, event_value)
            for _, event_path, actual in request_values
        ):
            continue
        state.facts[f"events.{event_type}.matched"] = True
        return True
    state.facts[f"events.{event_type}.count"] = matching_type_count
    state.facts[f"events.{event_type}.matched"] = False
    return False


@dataclass
class RequirementOutcome:
    has_prior_event: bool = False
    has_approval: bool = False
    missing_prior_event: bool = False
    missing_approval: bool = False
    unknown: bool = False


def _evaluate_requirements(
    rule: dict[str, Any],
    request: PolicyDecisionRequest,
    data: dict[str, Any],
    state: EvalState,
) -> RequirementOutcome:
    outcome = RequirementOutcome()
    requirements = rule.get("requires", [])
    if not isinstance(requirements, list):
        _mark_indeterminate(state, "invalid_requirements")
        outcome.unknown = True
        return outcome

    for requirement in requirements:
        if not isinstance(requirement, dict):
            _mark_indeterminate(state, "invalid_requirement")
            outcome.unknown = True
            continue
        kind = requirement.get("kind")
        if kind == "fact":
            supported = {"kind", "event_type", "fact", "op", "value", "match_arguments"}
            unknown_keys = set(requirement) - supported
            fact = requirement.get("fact")
            op = requirement.get("op")
            if (
                unknown_keys
                or requirement.get("event_type") is not None
                or requirement.get("match_arguments", []) != []
                or not isinstance(fact, str)
                or not fact
                or op not in ALLOWED_OPERATORS
            ):
                _mark_indeterminate(state, "invalid_fact_requirement")
                outcome.unknown = True
                continue
            result = evaluate_condition(
                {"kind": "predicate", "fact": fact, "op": op, "value": requirement.get("value")},
                data,
                state,
            )
            if result is False:
                # The decision contract has no separate "require_fact" outcome;
                # a known-unsatisfied prerequisite follows the prior-step branch.
                outcome.missing_prior_event = True
            elif result is None:
                outcome.unknown = True
            continue
        if kind not in {"prior_event", "approval"}:
            _mark_indeterminate(state, "unsupported_requirement")
            outcome.unknown = True
            continue
        if kind == "prior_event":
            outcome.has_prior_event = True
        else:
            outcome.has_approval = True
        result = _event_requirement_matches(requirement, rule, request, data, state)
        if result is False:
            if kind == "prior_event":
                outcome.missing_prior_event = True
            else:
                outcome.missing_approval = True
        elif result is None:
            outcome.unknown = True
    return outcome


def _default_approval_matches(
    rule: dict[str, Any],
    request: PolicyDecisionRequest,
    data: dict[str, Any],
    state: EvalState,
) -> bool | None:
    # The checked-in Northstar fixture predates explicit requirement metadata.
    # Preserve it with exact order/amount correlation while validating any supplied
    # tool, rule, status, and validity-window metadata.
    requirement = {
        "kind": "approval",
        "event_type": "approval.granted",
        "match_arguments": ["order_id", "amount"],
    }
    return _event_requirement_matches(
        requirement,
        rule,
        request,
        data,
        state,
        allow_legacy_approval=True,
    )


def _is_blocking_unknown(rule: dict[str, Any]) -> bool:
    return rule.get("severity") in BLOCKING_SEVERITIES


def _selected_result(
    decision: Decision,
    code: str,
    reason: str,
    selected: list[tuple[dict[str, Any], EvalState]],
    request: PolicyDecisionRequest,
) -> PolicyDecisionResult:
    rules = [rule for rule, _ in selected]
    facts = {key: value for _, state in selected for key, value in state.facts.items()}
    return _result(decision, code, reason, rules, facts, request)


def evaluate_policy(
    rules: list[dict[str, Any]],
    request: PolicyDecisionRequest,
    *,
    default_decision: Decision = "allow",
) -> PolicyDecisionResult:
    data = request.model_dump()
    matches: list[tuple[dict[str, Any], EvalState]] = []
    missing_prerequisites: list[tuple[dict[str, Any], EvalState]] = []
    approval_blocks: list[tuple[dict[str, Any], EvalState]] = []
    exception_allows: list[tuple[dict[str, Any], EvalState]] = []
    exception_not_applicable: list[tuple[dict[str, Any], EvalState]] = []
    indeterminate_rules: list[tuple[dict[str, Any], EvalState]] = []

    for rule in rules:
        if rule.get("status") != "approved" or rule.get("enforcement") != "guard":
            continue
        state = EvalState(facts={})

        targets = rule.get("target_tools", [])
        if not isinstance(targets, list) or not all(
            isinstance(target, str) and target for target in targets
        ):
            _mark_indeterminate(state, "invalid_target_tools")
            if _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue
        if targets and request.tool.name not in targets:
            continue

        scope_result = _scope_matches(rule, request, state)
        if scope_result is False:
            continue
        if scope_result is None:
            if _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue

        condition = rule.get("condition")
        if not isinstance(condition, dict):
            _mark_indeterminate(state, "invalid_condition_node")
            condition_result = None
        else:
            condition_result = evaluate_condition(condition, data, state)
        if condition_result is False:
            continue
        if condition_result is None:
            if _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue

        exception_result, exception_effect = _exception_applies(rule, data, state)
        if exception_result is True:
            selected = (rule, state)
            if exception_effect == "allow":
                exception_allows.append(selected)
            else:
                exception_not_applicable.append(selected)
            continue
        if exception_result is None:
            if _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue

        requirements = _evaluate_requirements(rule, request, data, state)
        effect = rule.get("effect")
        if requirements.missing_prior_event:
            missing_prerequisites.append((rule, state))
        if requirements.missing_approval:
            approval_blocks.append((rule, state))
        if requirements.missing_prior_event or requirements.missing_approval:
            if (
                effect == "require_prior_event"
                and not requirements.has_prior_event
                and not requirements.missing_prior_event
            ):
                missing_prerequisites.append((rule, state))
            if (
                effect == "require_approval"
                and not requirements.has_approval
                and not requirements.missing_approval
            ):
                approval_blocks.append((rule, state))
            continue
        if requirements.unknown:
            if _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue

        if effect == "require_prior_event":
            if not requirements.has_prior_event:
                missing_prerequisites.append((rule, state))
            continue
        if effect == "require_approval":
            if requirements.has_approval:
                continue
            approval_result = _default_approval_matches(rule, request, data, state)
            if approval_result is False:
                approval_blocks.append((rule, state))
            elif approval_result is None and _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue
        if effect == "observe_only":
            continue
        if effect not in SUPPORTED_EFFECTS:
            _mark_indeterminate(state, f"unsupported_effect:{effect}")
            if _is_blocking_unknown(rule):
                indeterminate_rules.append((rule, state))
            continue
        matches.append((rule, state))

    # A known deny is final. Otherwise fail closed on uncertainty, then route the
    # caller through missing prerequisites and approvals before considering allows.
    denied = [(rule, state) for rule, state in matches if rule.get("effect") == "deny"]
    if denied:
        return _selected_result(
            "deny",
            "rule_denied",
            "A covered rule denies this tool call.",
            denied,
            request,
        )

    if indeterminate_rules:
        rule, state = indeterminate_rules[0]
        return _result(
            "indeterminate",
            "fail_closed_unknown_fact",
            state.indeterminate or "Policy evaluation could not be completed safely.",
            [rule],
            state.facts,
            request,
        )

    if missing_prerequisites:
        return _selected_result(
            "require_prior_event",
            "required_event_missing",
            "A prerequisite or required prior event is missing.",
            missing_prerequisites,
            request,
        )

    if approval_blocks:
        return _selected_result(
            "require_approval",
            "approval_required",
            "Matching supervisor approval is required before execution.",
            approval_blocks,
            request,
        )

    allowed = [
        (rule, state) for rule, state in matches if rule.get("effect") == "allow"
    ] + exception_allows
    if allowed:
        return _selected_result(
            "allow",
            "rule_allowed",
            "A covered rule explicitly allows this tool call.",
            allowed,
            request,
        )

    if exception_not_applicable and default_decision == "allow":
        return _selected_result(
            "not_applicable",
            "rule_exception",
            "A matching exception makes the covered rule inapplicable.",
            exception_not_applicable,
            request,
        )

    return _result(
        default_decision,
        f"default_{default_decision}",
        "No blocking rule applies.",
        [],
        {},
        request,
    )


def _result(
    decision: Decision,
    code: str,
    reason: str,
    rules: list[dict[str, Any]],
    facts: dict[str, Any],
    request: PolicyDecisionRequest,
    rule_ids: list[str] | None = None,
) -> PolicyDecisionResult:
    ids = (
        rule_ids if rule_ids is not None else [rule.get("stable_key", "unknown") for rule in rules]
    )
    payload = {
        "decision": decision,
        "reason_code": code,
        "rule_ids": ids,
        "facts": facts,
        "request": request.model_dump(),
    }
    return PolicyDecisionResult(
        decision=decision,
        reason_code=code,
        reason=reason,
        rule_ids=ids,
        evaluated_facts=facts,
        decision_hash=content_hash(payload),
    )
