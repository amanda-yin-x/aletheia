from __future__ import annotations

from typing import Any

from app.services.canonical import token_estimate

ESTIMATOR_NAME = "char_div_4"
ESTIMATOR_VERSION = "1.0.0"
SEVERITY_WEIGHTS = {"low": 1, "medium": 2, "high": 4, "critical": 8}


def content_size(value: str) -> dict[str, int]:
    return {
        "lines": len(value.splitlines()),
        "characters": len(value),
        "utf8_bytes": len(value.encode("utf-8")),
        "estimated_tokens": token_estimate(value),
    }


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def compilation_metrics(
    *,
    baseline: str,
    artifacts: dict[str, str],
    kernel_path: str,
    skill_paths: list[str],
    knowledge_paths: list[str],
    machine_paths: list[str],
    expected_context_paths: list[str],
    routing_entries: list[dict[str, Any]],
    literal_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    sizes = {path: content_size(value) for path, value in sorted(artifacts.items())}
    expected_paths = [path for path in expected_context_paths if path in artifacts]
    expected_text = "".join(artifacts[path] for path in expected_paths)
    bundle_text = "".join(artifacts[path] for path in sorted(artifacts))
    active = [entry for entry in routing_entries if entry["disposition"] != "retired"]
    approved = [entry for entry in active if entry["rule_status"] == "approved"]
    routed = [entry for entry in active if entry["disposition"] in {"routed", "unsupported", "blocked"}]
    anchored = [
        entry
        for entry in active
        if entry["provenance_kind"] == "reviewer_authored_guidance"
        or entry["verified_source_anchors"] > 0
    ]
    preserved_keys = {
        item["rule_key"] for item in literal_checks if item["preserved"]
    }
    approved_preserved = [
        entry for entry in approved if entry["rule_key"] in preserved_keys
    ]
    weighted_total = sum(SEVERITY_WEIGHTS[entry["severity"]] for entry in approved)
    weighted_preserved = sum(
        SEVERITY_WEIGHTS[entry["severity"]]
        for entry in approved_preserved
    )
    high_critical = [entry for entry in approved if entry["severity"] in {"high", "critical"}]
    guard_and_test = [
        entry
        for entry in high_critical
        if {"pre_tool_policy", "test"}.issubset(set(entry["destinations"]))
    ]
    return {
        "schema_version": "1.0",
        "estimator": {"name": ESTIMATOR_NAME, "version": ESTIMATOR_VERSION},
        "baseline_always_loaded": content_size(baseline),
        "compiled_kernel": sizes.get(kernel_path, content_size("")),
        "skills": {path: sizes[path] for path in skill_paths if path in sizes},
        "knowledge": {path: sizes[path] for path in knowledge_paths if path in sizes},
        "machine_enforced": {path: sizes[path] for path in machine_paths if path in sizes},
        "total_bundle_without_manifest": content_size(bundle_text),
        "expected_per_task_context": {
            **content_size(expected_text),
            "artifact_paths": expected_paths,
        },
        "routing": {
            "active_normative_clauses": len(active),
            "explicit_dispositions": len(routed),
            "routing_coverage": _ratio(len(routed), len(active)),
            "verified_source_anchor_coverage": _ratio(len(anchored), len(active)),
            "approved_preservation": _ratio(len(approved_preserved), len(approved)),
            "severity_weighted_approved_preservation": _ratio(
                weighted_preserved, weighted_total
            ),
            "high_critical_guard_and_test_placement": _ratio(
                len(guard_and_test), len(high_critical)
            ),
            "blocked_count": sum(entry["disposition"] == "blocked" for entry in active),
            "unsupported_count": sum(entry["disposition"] == "unsupported" for entry in active),
            "unrouted_count": sum(not entry["destinations"] for entry in active),
            "unresolved_count": sum(entry["rule_status"] != "approved" for entry in active),
        },
        "protected_literals": literal_checks,
        "behavioral_fidelity": "not_measured",
        "interpretation": (
            "Deterministic routing, source-anchor verification, and literal checks "
            "are conformance evidence; they do not measure behavioral fidelity."
        ),
    }
