from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Build, Run, ScenarioResult, TestCase, TraceEventModel
from app.schemas import (
    BuildManifest,
    DatasetManifest,
    FactFixture,
    PolicyArtifact,
    PolicyDecisionRequest,
    RegressionArtifact,
    ToolRegistry,
    TraceEvent,
)
from app.services.canonical import (
    artifact_bytes,
    artifact_hash,
    bytes_hash,
    canonical_json_bytes,
)
from app.services.compiler import (
    FACT_ARTIFACT,
    POLICY_ARTIFACT,
    ROOT_ARTIFACT,
    TEST_ARTIFACT,
    TOOL_ARTIFACT,
)
from app.services.errors import ServiceError
from app.services.policy import evaluate_policy

ARMS = ["baseline_unenforced", "compiled_unenforced", "compiled_enforced"]
RUNNER_VERSION = "0.3.0"
DRAFT_2020_12_URI = "https://json-schema.org/draft/2020-12/schema"


@dataclass(frozen=True)
class FixtureToolContract:
    validator: Draft202012Validator
    mutating: bool


def _event(
    events: list[dict[str, Any]],
    type_: str,
    payload: dict[str, Any],
    rule_ids: list[str] | None = None,
) -> None:
    events.append(
        {
            "sequence": len(events) + 1,
            "type": type_,
            "payload": payload,
            "rule_ids": rule_ids or [],
            "duration_ms": 0.0,
        }
    )


def _execute(
    name: str,
    arguments: dict[str, Any],
    state: dict[str, Any],
    *,
    mutating: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = deepcopy(state)
    if name == "issue_refund":
        state.setdefault("refunds", []).append(
            {
                "order_id": arguments["order_id"],
                "item_id": arguments["item_id"],
                "amount": arguments["amount"],
                "destination": arguments["destination"],
            }
        )
        state["refunded"] = True
        result = {"status": "refunded", "amount": arguments["amount"]}
    elif name == "request_supervisor_approval":
        state.setdefault("approvals", []).append({"status": "pending", **arguments})
        result = {"status": "approval_pending", **arguments}
    elif name == "escalate_case":
        state.setdefault("escalations", []).append(arguments)
        result = {
            "status": "escalated",
            "case_id": f"CASE-{len(state['escalations']):04d}",
        }
    elif name in {"get_order", "get_customer"}:
        result = {"status": "found", "data_scope": "evaluation"}
    elif name == "book_callback":
        state.setdefault("callbacks", []).append(arguments)
        result = {"status": "booked"}
    elif name == "cancel_item":
        state.setdefault("cancelled_items", []).append(arguments["item_id"])
        result = {"status": "cancelled"}
    elif not mutating:
        result = {"status": "fixture_recorded", "data_scope": "evaluation"}
    else:
        # Domain packs never execute customer code or external tools. Unknown
        # fixture mutations are represented by one generic, deterministic
        # recorder so a second domain uses the same runner without semantic
        # branches or real-world side effects.
        state.setdefault("fixture_mutations", []).append(
            {"tool": name, "arguments": deepcopy(arguments)}
        )
        result = {"status": "fixture_recorded", "tool": name}
    diff = {
        key: {"before": before.get(key), "after": value}
        for key, value in state.items()
        if before.get(key) != value
    }
    return result, diff


def _registry_contracts(
    registry: dict[str, Any],
) -> dict[str, FixtureToolContract]:
    rows = registry.get("tools")
    if (
        registry.get("schema_version") != "0.2"
        or registry.get("schema_dialect") != DRAFT_2020_12_URI
        or not isinstance(rows, list)
    ):
        raise ServiceError(
            "build_tool_registry_invalid",
            "The build-pinned tool registry is malformed.",
            status_code=409,
        )
    contracts: dict[str, FixtureToolContract] = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or not isinstance(row.get("mutating"), bool)
        ):
            raise ServiceError(
                "build_tool_registry_invalid",
                "The build-pinned tool registry is malformed.",
                status_code=409,
            )
        name = row["name"]
        input_schema = row.get("input_schema")
        if (
            name in contracts
            or not isinstance(input_schema, dict)
            or input_schema.get("$schema") != DRAFT_2020_12_URI
            or input_schema.get("type") != "object"
            or input_schema.get("additionalProperties") is not False
        ):
            raise ServiceError(
                "build_tool_registry_invalid",
                "The build-pinned tool registry contains an invalid contract.",
                status_code=409,
            )
        try:
            Draft202012Validator.check_schema(input_schema)
        except SchemaError as error:
            raise ServiceError(
                "build_tool_registry_invalid",
                "The build-pinned tool registry contains an invalid JSON Schema.",
                status_code=409,
            ) from error
        contracts[name] = FixtureToolContract(
            validator=Draft202012Validator(input_schema),
            mutating=row["mutating"],
        )
    return contracts


def _validation_error(
    name: Any,
    arguments: Any,
    contracts: dict[str, FixtureToolContract],
) -> dict[str, Any] | None:
    if not isinstance(name, str) or not name:
        return {"code": "malformed_tool_name", "message": "Tool name must be text."}
    if name not in contracts:
        return {"code": "unknown_tool", "message": "Tool is not in the pinned registry."}
    if not isinstance(arguments, dict):
        return {
            "code": "malformed_tool_arguments",
            "message": "Tool arguments must be an object.",
        }
    errors = sorted(
        contracts[name].validator.iter_errors(arguments),
        key=lambda error: (
            {"required": 0, "type": 1, "additionalProperties": 2}.get(str(error.validator), 3),
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )
    if not errors:
        return None
    error = errors[0]
    path_parts = list(error.absolute_path)
    path = [str(part) for part in path_parts]
    container: Any = arguments
    for part in path_parts:
        if isinstance(container, dict):
            container = container.get(part)
        elif isinstance(container, list) and isinstance(part, int) and part < len(container):
            container = container[part]
        else:
            container = None
            break
    if error.validator == "required":
        required = error.validator_value if isinstance(error.validator_value, list) else []
        missing = sorted(
            item
            for item in required
            if isinstance(item, str) and (not isinstance(container, dict) or item not in container)
        )
        return {
            "code": "missing_required_arguments",
            "message": "Required tool arguments are missing.",
            "path": path,
            "missing": missing,
        }
    if error.validator == "type":
        return {
            "code": "invalid_tool_argument_type",
            "message": "A tool argument has the wrong type.",
            "path": path,
            "expected": error.validator_value,
        }
    if error.validator == "additionalProperties":
        properties = error.schema.get("properties", {})
        allowed = set(properties) if isinstance(properties, dict) else set()
        unexpected = (
            sorted(str(key) for key in container if key not in allowed)
            if isinstance(container, dict)
            else []
        )
        return {
            "code": "unexpected_tool_arguments",
            "message": "Tool arguments contain fields outside the pinned schema.",
            "path": path,
            "unexpected": unexpected,
        }
    return {
        "code": "invalid_tool_arguments",
        "message": "Tool arguments do not satisfy the pinned schema.",
        "path": path,
        "constraint": str(error.validator),
    }


def _base_rule_key(value: str) -> str:
    return value.split("@", 1)[0]


def _compiler_assertion(
    assertion: dict[str, Any], compiler_context: dict[str, Any]
) -> dict[str, Any]:
    kind = assertion.get("kind")
    if kind == "artifact_contains":
        path = assertion.get("artifact")
        needle = assertion.get("text")
        artifact = compiler_context.get("artifacts", {}).get(path)
        passed = isinstance(artifact, str) and isinstance(needle, str) and needle in artifact
        return {
            "kind": kind,
            "artifact": path,
            "passed": passed,
            "reason": "text_found" if passed else "text_not_found",
        }
    if kind == "finding":
        manifest = compiler_context.get("manifest", {})
        findings = [
            *manifest.get("unresolved_findings", []),
            *manifest.get("accepted_findings", []),
        ]
        expected_rules = set(assertion.get("related_rules", []))
        matched = None
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            related = {_base_rule_key(str(value)) for value in finding.get("related_rules", [])}
            if (
                finding.get("type") == assertion.get("type")
                and expected_rules <= related
                and finding.get("resolution_state") == assertion.get("resolution_state")
            ):
                matched = finding
                break
        return {
            "kind": kind,
            "finding_type": assertion.get("type"),
            "passed": matched is not None,
            "reason": "finding_matched" if matched is not None else "finding_not_matched",
        }
    if kind == "artifact_digest":
        path = assertion.get("artifact")
        artifact = compiler_context.get("artifacts", {}).get(path)
        actual = artifact_hash(artifact) if artifact is not None else None
        passed = actual == assertion.get("sha256")
        return {
            "kind": kind,
            "artifact": path,
            "actual_sha256": actual,
            "passed": passed,
            "reason": "digest_matched" if passed else "digest_mismatch",
        }
    return {
        "kind": str(kind or "missing"),
        "passed": False,
        "reason": "unsupported_compiler_assertion",
    }


def run_scenario(
    spec: dict[str, Any],
    arm: str,
    policy_rules: list[dict[str, Any]],
    tool_registry: dict[str, Any] | None = None,
    compiler_context: dict[str, Any] | None = None,
    request_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str]:
    state = deepcopy(spec["initial_state"])
    initial_hash = bytes_hash(canonical_json_bytes(state))
    events: list[dict[str, Any]] = []
    _event(
        events,
        "run_started",
        {
            "arm": arm,
            "adapter": "deterministic_replay",
            "initial_state_hash": initial_hash,
        },
    )
    messages = spec.get("messages", [])
    if messages:
        _event(events, "user_message", messages[0])

    trajectory = spec.get("scripted_trajectories", {}).get(arm, [])
    if tool_registry is None:
        inferred_properties: dict[str, set[str]] = {}
        for step in trajectory:
            if (
                not isinstance(step, dict)
                or step.get("type") != "tool_call"
                or not isinstance(step.get("name"), str)
            ):
                continue
            inferred_properties.setdefault(step["name"], set())
            inferred_arguments = step.get("arguments")
            if isinstance(inferred_arguments, dict):
                inferred_properties[step["name"]].update(
                    key for key in inferred_arguments if isinstance(key, str)
                )
        tool_registry = {
            "schema_version": "0.2",
            "schema_dialect": DRAFT_2020_12_URI,
            "tools": [
                {
                    "name": name,
                    "mutating": name not in {"get_customer", "get_order"},
                    "input_schema": {
                        "$schema": DRAFT_2020_12_URI,
                        "type": "object",
                        "properties": {key: {} for key in sorted(inferred_properties[name])},
                        "additionalProperties": False,
                    },
                }
                for name in sorted(inferred_properties)
            ],
        }
    contracts = _registry_contracts(tool_registry)
    compiler_context = compiler_context or {"artifacts": {}, "manifest": {}}

    executed: list[str] = []
    proposed: list[str] = []
    decisions: list[str] = []
    policy_block_count = 0
    validation_errors: list[dict[str, Any]] = []
    for step in trajectory:
        if not isinstance(step, dict) or step.get("type") != "tool_call":
            continue
        name = step.get("name")
        arguments = step.get("arguments", {})
        proposed.append(str(name))
        _event(
            events,
            "tool_proposed",
            {"name": name, "arguments": arguments, "status": "proposed"},
        )
        invalid = _validation_error(name, arguments, contracts)
        if invalid is not None:
            payload = {
                **invalid,
                "name": name,
                "state_mutated": False,
            }
            validation_errors.append(payload)
            _event(events, "error", payload)
            continue
        assert isinstance(name, str) and isinstance(arguments, dict)
        decision = evaluate_policy(
            policy_rules,
            PolicyDecisionRequest.model_validate(
                {
                    "tool": {"name": name, "arguments": arguments},
                    "state": state,
                    "context": request_context or {},
                    "events": spec.get("events", []),
                }
            ),
        )
        decisions.append(decision.decision)
        _event(events, "policy_evaluated", decision.model_dump(), decision.rule_ids)
        enforced = arm == "compiled_enforced"
        if enforced and decision.decision not in {"allow", "not_applicable"}:
            event_type = (
                "approval_required" if decision.decision == "require_approval" else "tool_blocked"
            )
            _event(
                events,
                event_type,
                {
                    "name": name,
                    "decision": decision.decision,
                    "state_mutated": False,
                    "reason_code": decision.reason_code,
                },
                decision.rule_ids,
            )
            policy_block_count += 1
            continue
        result, diff = _execute(
            name,
            arguments,
            state,
            mutating=contracts[name].mutating,
        )
        _event(
            events,
            "tool_executed",
            {"name": name, "arguments": arguments, "status": "executed"},
        )
        executed.append(name)
        _event(events, "tool_result", {"name": name, "result": result})
        if diff:
            _event(events, "state_changed", {"name": name, "diff": diff})

    expected = spec.get("expected", {})
    target_decision = expected.get("guarded_decision", "allow")
    forbidden = set(expected.get("forbidden_executed_tools", []))
    attempted_violation = any(
        value in {"deny", "require_approval", "require_prior_event", "indeterminate"}
        for value in decisions
    )
    executed_violation = bool(forbidden.intersection(executed))
    assertion_results = [
        _compiler_assertion(assertion, compiler_context)
        for assertion in expected.get("assertions", [])
        if isinstance(assertion, dict)
    ]
    if proposed:
        if arm == "compiled_enforced":
            actual = decisions[-1] if decisions else None
            tool_passed = (
                not validation_errors
                and actual == target_decision
                and not executed_violation
                and (
                    target_decision not in {"allow", "not_applicable"}
                    or len(executed) == len(proposed)
                )
            )
        else:
            tool_passed = (
                not validation_errors and not executed_violation and len(executed) == len(proposed)
            )
        assertion_results.append(
            {
                "kind": "tool_outcome",
                "expected_guarded_decision": target_decision,
                "actual_policy_decision": decisions[-1] if decisions else None,
                "forbidden_executed_tools": sorted(forbidden),
                "passed": tool_passed,
                "reason": "tool_outcome_matched" if tool_passed else "tool_outcome_mismatch",
            }
        )
    if not assertion_results:
        assertion_results.append(
            {
                "kind": "explicit_assertion_required",
                "passed": False,
                "reason": "scenario_has_no_executable_or_compiler_assertion",
            }
        )
        _event(
            events,
            "error",
            {
                "code": "vacuous_scenario",
                "message": "The scenario has no explicit assertion.",
                "state_mutated": False,
            },
        )
    task_success = all(bool(item.get("passed")) for item in assertion_results)
    metrics = {
        "task_success": task_success,
        "proposed_calls": len(proposed),
        "executed_calls": len(executed),
        "attempted_violation": attempted_violation,
        "executed_violation": executed_violation,
        "blocked_calls": policy_block_count,
        "tool_validation_errors": len(validation_errors),
        "false_block": target_decision == "allow" and policy_block_count > 0,
        "assertion_count": len(assertion_results),
        "assertions": assertion_results,
        "initial_state_hash": initial_hash,
        "tokens": None,
        "cost": None,
    }
    _event(
        events,
        "assertion_evaluated",
        {
            "expected_decision": target_decision,
            "passed": task_success,
            "executed_violation": executed_violation,
            "assertions": assertion_results,
        },
    )
    final_state_hash = bytes_hash(canonical_json_bytes(state))
    _event(
        events,
        "run_finished",
        {
            "verdict": "passed" if task_success else "failed",
            "final_state_hash": final_state_hash,
        },
    )
    if validation_errors:
        divergence = (
            "The proposed call failed validation against the build-pinned tool registry; "
            "policy evaluation and execution were skipped."
        )
    elif arm == "compiled_enforced" and attempted_violation and proposed:
        divergence = (
            f"Policy adapter intercepted {proposed[-1]} before tool execution; "
            "state mutation was prevented."
        )
    else:
        divergence = "No material divergence from the expected case trajectory."
    return events, state, metrics, divergence


def _coverage_dimension(eligible: set[str], covered: set[str]) -> dict[str, Any]:
    actual = eligible & covered
    return {
        "eligible_count": len(eligible),
        "covered_count": len(actual),
        "ratio": round(len(actual) / len(eligible), 4) if eligible else 1.0,
        "uncovered": sorted(eligible - actual),
    }


def _aggregate(
    results: list[ScenarioResult],
    specs: list[dict[str, Any]],
    input_manifest: dict[str, Any],
) -> dict[str, Any]:
    by_arm: dict[str, list[ScenarioResult]] = {arm: [] for arm in ARMS}
    for result in results:
        by_arm[result.arm].append(result)
    output: dict[str, Any] = {}
    for arm, rows in by_arm.items():
        total = len(rows)
        output[arm] = {
            "cases": total,
            "task_success_rate": (
                round(sum(bool(row.metrics.get("task_success")) for row in rows) / total, 4)
                if total
                else 0.0
            ),
            "attempted_violation_rate": (
                round(
                    sum(bool(row.metrics.get("attempted_violation")) for row in rows) / total,
                    4,
                )
                if total
                else 0.0
            ),
            "executed_violation_rate": (
                round(
                    sum(bool(row.metrics.get("executed_violation")) for row in rows) / total,
                    4,
                )
                if total
                else 0.0
            ),
            "false_block_rate": (
                round(sum(bool(row.metrics.get("false_block")) for row in rows) / total, 4)
                if total
                else 0.0
            ),
            "tool_validation_error_rate": (
                round(
                    sum(int(row.metrics.get("tool_validation_errors", 0)) for row in rows) / total,
                    4,
                )
                if total
                else 0.0
            ),
            "input_tokens": None,
            "output_tokens": None,
            "cost": None,
        }
    tag_counts = {
        tag: sum(tag in spec.get("tags", []) for spec in specs)
        for tag in ("positive", "negative", "boundary")
    }
    executable_cases = sum(
        any(
            isinstance(step, dict) and step.get("type") == "tool_call"
            for steps in spec.get("scripted_trajectories", {}).values()
            for step in steps
        )
        for spec in specs
    )
    compiler_assertion_cases = sum(
        bool(spec.get("expected", {}).get("assertions")) for spec in specs
    )
    explicit_cases = sum(
        bool(spec.get("expected", {}).get("assertions"))
        or any(
            isinstance(step, dict) and step.get("type") == "tool_call"
            for steps in spec.get("scripted_trajectories", {}).values()
            for step in steps
        )
        for spec in specs
    )
    total_specs = len(specs)
    non_executable_cases = total_specs - executable_cases
    rule_inputs = [
        rule
        for rule in input_manifest.get("rules", [])
        if isinstance(rule, dict) and isinstance(rule.get("stable_key"), str)
    ]
    test_required_rules = {
        str(placement["rule_stable_key"])
        for placement in input_manifest.get("placements", [])
        if isinstance(placement, dict)
        and isinstance(placement.get("rule_stable_key"), str)
        and "test" in placement.get("destinations", [])
    }
    retired_rules = {
        str(placement["rule_stable_key"])
        for placement in input_manifest.get("placements", [])
        if isinstance(placement, dict)
        and isinstance(placement.get("rule_stable_key"), str)
        and placement.get("disposition") == "retired"
    }
    accepted_rules = {
        str(rule["stable_key"])
        for rule in rule_inputs
        if rule.get("status") == "approved" and rule.get("stable_key") in test_required_rules
    }
    test_tags_by_rule: dict[str, set[str]] = {}
    for test in input_manifest.get("tests", []):
        if not isinstance(test, dict):
            continue
        tags = {str(tag) for tag in test.get("tags", []) if isinstance(tag, str)}
        for rule_id in test.get("rule_ids", []):
            if isinstance(rule_id, str):
                test_tags_by_rule.setdefault(rule_id, set()).update(tags)
    tested_rules = set(test_tags_by_rule)
    normative_sources = {
        str(source)
        for rule in rule_inputs
        if rule.get("status") == "approved" and rule.get("stable_key") in test_required_rules
        for source in rule.get("source_documents", [])
        if isinstance(source, str)
    }
    covered_sources = {
        str(source)
        for rule in rule_inputs
        if rule.get("status") == "approved"
        and rule.get("stable_key") in test_required_rules
        and rule.get("stable_key") in tested_rules
        for source in rule.get("source_documents", [])
        if isinstance(source, str)
    }
    boundary_rules = {
        str(rule["stable_key"])
        for rule in rule_inputs
        if rule.get("status") == "approved" and rule.get("enforcement") == "guard"
    }
    boundary_covered = {
        key
        for key in boundary_rules
        if "boundary" in test_tags_by_rule.get(key, set())
        or {"positive", "negative"} <= test_tags_by_rule.get(key, set())
    }
    critical_unclassified = sorted(
        str(rule["stable_key"])
        for rule in rule_inputs
        if rule.get("severity") == "critical"
        and rule.get("stable_key") not in retired_rules
        and (rule.get("status") != "approved" or rule.get("stable_key") not in tested_rules)
    )
    output["coverage"] = {
        "test_count": total_specs,
        "arms": len(ARMS),
        "tag_counts": tag_counts,
        "positive_negative_boundary": all(tag_counts.values()),
        "executable_case_count": executable_cases,
        "compiler_assertion_case_count": compiler_assertion_cases,
        "explicit_assertion_case_count": explicit_cases,
        "explicit_assertion_coverage": (
            round(explicit_cases / total_specs, 4) if total_specs else 0.0
        ),
        "compiler_assertion_coverage": (
            round(compiler_assertion_cases / non_executable_cases, 4)
            if non_executable_cases
            else 1.0
        ),
        "declared_rule_linkage": _coverage_dimension(accepted_rules, tested_rules),
        "declared_source_linkage": _coverage_dimension(normative_sources, covered_sources),
        "declared_boundary_linkage": _coverage_dimension(boundary_rules, boundary_covered),
        "critical_unclassified_rules": critical_unclassified,
    }
    return output


def _json_artifact(build: Build, path: str) -> dict[str, Any]:
    value = build.artifacts.get(path)
    try:
        loaded = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as error:
        raise ServiceError(
            "build_integrity_invalid",
            f"Build artifact {path} is not valid JSON.",
            status_code=409,
        ) from error
    if not isinstance(loaded, dict):
        raise ServiceError(
            "build_integrity_invalid",
            f"Build artifact {path} must contain an object.",
            status_code=409,
        )
    return loaded


def _load_build_bundle(
    build: Build,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    manifest = _json_artifact(build, ROOT_ARTIFACT)
    root_bytes = artifact_bytes(build.artifacts[ROOT_ARTIFACT])
    if bytes_hash(root_bytes) != build.content_hash:
        raise ServiceError(
            "build_integrity_invalid",
            "The build root does not match manifest.json bytes.",
            status_code=409,
        )
    try:
        manifest = BuildManifest.model_validate(manifest).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
    except ValidationError as error:
        raise ServiceError(
            "build_integrity_invalid",
            "The build manifest violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    artifact_hashes = manifest.get("artifact_hashes")
    if not isinstance(artifact_hashes, dict):
        raise ServiceError(
            "build_integrity_invalid",
            "The build manifest has no artifact digest map.",
            status_code=409,
        )
    expected_members = set(build.artifacts) - {ROOT_ARTIFACT}
    if set(artifact_hashes) != expected_members:
        raise ServiceError(
            "build_integrity_invalid",
            "The build manifest does not cover every emitted non-root artifact.",
            status_code=409,
        )
    for path in sorted(expected_members):
        if artifact_hash(build.artifacts[path]) != artifact_hashes[path]:
            raise ServiceError(
                "build_integrity_invalid",
                f"Build artifact {path} failed digest verification.",
                status_code=409,
            )
    inputs = manifest.get("inputs")
    if (
        not isinstance(inputs, dict)
        or bytes_hash(canonical_json_bytes(inputs)) != manifest.get("input_hash")
        or manifest.get("input_hash") != build.input_hash
    ):
        raise ServiceError(
            "build_integrity_invalid",
            "The build input manifest failed digest verification.",
            status_code=409,
        )
    policy = _json_artifact(build, POLICY_ARTIFACT)
    registry = _json_artifact(build, TOOL_ARTIFACT)
    facts = _json_artifact(build, FACT_ARTIFACT)
    try:
        registry = ToolRegistry.model_validate(registry).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        facts = FactFixture.model_validate(facts).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
    except ValidationError as error:
        raise ServiceError(
            "build_integrity_invalid",
            "A build-pinned tool or fact fixture violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    regression_value = build.artifacts.get(TEST_ARTIFACT)
    try:
        regression = (
            yaml.safe_load(regression_value)
            if isinstance(regression_value, str)
            else regression_value
        )
    except yaml.YAMLError as error:
        raise ServiceError(
            "build_integrity_invalid",
            "The build-pinned regression suite is invalid.",
            status_code=409,
        ) from error
    try:
        validated_regression = RegressionArtifact.model_validate(regression)
        validated_policy = PolicyArtifact.model_validate(policy)
    except ValidationError as error:
        raise ServiceError(
            "build_integrity_invalid",
            "A build-pinned policy or test violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    tests = [record.model_dump(mode="json", by_alias=True) for record in validated_regression.tests]
    rules = [rule.model_dump(mode="json", by_alias=True) for rule in validated_policy.rules]
    _registry_contracts(registry)
    return manifest, tests, rules, registry, facts


async def run_comparison(
    session: AsyncSession,
    project_id: str,
    build_id: str | None = None,
    *,
    run_id: str | None = None,
) -> Run:
    if run_id:
        existing_run = await session.get(Run, run_id)
        if (
            existing_run
            and existing_run.project_id == project_id
            and existing_run.status == "succeeded"
        ):
            return existing_run
    build = (
        await session.get(Build, build_id)
        if build_id
        else await session.scalar(
            select(Build).where(Build.project_id == project_id).order_by(Build.created_at.desc())
        )
    )
    if not build:
        raise ServiceError(
            "build_required",
            "Build a candidate before running the comparison.",
            status_code=409,
        )
    if build.project_id != project_id:
        raise ServiceError("build_not_found", "Build not found.", status_code=404)
    manifest, test_records, policy_rules, registry, facts = _load_build_bundle(build)

    current_tests = {
        test.stable_key: test
        for test in (
            await session.scalars(select(TestCase).where(TestCase.project_id == project_id))
        ).all()
    }
    pinned_keys = [str(record.get("stable_key", "")) for record in test_records]
    if len(set(pinned_keys)) != len(pinned_keys) or any(
        key not in current_tests for key in pinned_keys
    ):
        raise ServiceError(
            "build_test_mapping_invalid",
            "The build-pinned suite cannot be mapped to project-owned test records.",
            status_code=409,
        )
    artifact_hashes = manifest["artifact_hashes"]
    suite = yaml.safe_load(build.artifacts[TEST_ARTIFACT]).get("suite", {})
    specs = [record["spec"] for record in test_records]
    dataset_payload = {
        "schema_version": "0.3",
        "name": suite.get("name", "Aletheia-authored refund boundary suite"),
        "version": suite.get("version", "2"),
        "data_scope": suite.get("data_scope", "evaluation"),
        "provenance": suite.get("provenance", "aletheia_authored_v1"),
        "test_count": len(specs),
        "tests_sha256": artifact_hashes[TEST_ARTIFACT],
        "tools_sha256": artifact_hashes[TOOL_ARTIFACT],
        "facts_sha256": artifact_hashes[FACT_ARTIFACT],
        "facts_source": manifest["inputs"]["facts"]["source"],
        "contains_customer_records": facts.get("contains_customer_records"),
        "evaluation_timestamp": facts["evaluation_timestamp"],
        "build_root_sha256": build.content_hash,
        "runner_version": RUNNER_VERSION,
    }
    dataset_manifest = DatasetManifest.model_validate(
        {
            **dataset_payload,
            "hash": bytes_hash(canonical_json_bytes(dataset_payload)),
        }
    ).model_dump(mode="json", by_alias=True)
    run = Run(
        id=run_id or str(uuid4()),
        project_id=project_id,
        build_id=build.id,
        requested_arms=ARMS,
        adapter="fixture",
        model=None,
        dataset_manifest=dataset_manifest,
        status="running",
        metrics={},
    )
    session.add(run)
    await session.flush()
    result_rows: list[ScenarioResult] = []
    compiler_context = {"artifacts": build.artifacts, "manifest": manifest}
    for record in test_records:
        spec = record["spec"]
        stable_key = str(record["stable_key"])
        current_test = current_tests[stable_key]
        snapshot = {
            "stable_key": stable_key,
            "title": str(record["title"]),
            "rule_ids": list(spec.get("rule_ids", [])),
            "tags": list(spec.get("tags", [])),
            "provenance": str(record.get("provenance", spec.get("provenance", ""))),
            "spec_digest": artifact_hash(spec),
        }
        for arm in ARMS:
            events, state, metrics, divergence = run_scenario(
                spec,
                arm,
                policy_rules,
                registry,
                compiler_context,
                {
                    "domain": manifest["inputs"]["runtime"]["domain"],
                    "lifecycle": manifest["inputs"]["runtime"]["lifecycle"],
                    "now": facts["evaluation_timestamp"],
                },
            )
            result = ScenarioResult(
                run_id=run.id,
                test_case_id=current_test.id,
                test_snapshot=snapshot,
                arm=arm,
                verdict="passed" if metrics["task_success"] else "failed",
                metrics=metrics,
                final_state_hash=bytes_hash(canonical_json_bytes(state)),
                first_divergence=divergence,
                trace_id=str(uuid4()),
            )
            session.add(result)
            await session.flush()
            for item in events:
                TraceEvent.model_validate(item)
                session.add(
                    TraceEventModel(
                        result_id=result.id,
                        trace_id=result.trace_id,
                        **item,
                    )
                )
            result_rows.append(result)
    run.metrics = _aggregate(result_rows, specs, manifest["inputs"])
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run
