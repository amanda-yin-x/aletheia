from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import get_settings
from app.schemas import CompilerProfile
from app.services.canonical import bytes_hash, canonical_json_bytes
from app.services.errors import ServiceError

PROFILE_SCHEMA_VERSION = "1.0"
KNOWN_DESTINATIONS = {
    "prompt_kernel",
    "skill",
    "knowledge",
    "pre_tool_policy",
    "test",
    "human_review",
    "unsupported",
}
KNOWN_TRANSFORM_KINDS = {
    "verbatim",
    "reviewed_normalization",
    "reviewer_authored_guidance",
    "compiler_scaffold",
}


@dataclass(frozen=True)
class LoadedCompilerProfile:
    name: str
    version: str
    path: str
    digest: str
    value: dict[str, Any]
    project: dict[str, Any]
    project_digest: str


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ServiceError(
            "compiler_profile_invalid",
            f"The compiler profile requires a non-empty {key}.",
            status_code=409,
        )
    return item


def _string_list(value: Any, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ServiceError(
            "compiler_profile_invalid",
            f"The compiler profile field {field} must be a non-empty string list.",
            status_code=409,
        )
    if len(value) != len(set(value)):
        raise ServiceError(
            "compiler_profile_invalid",
            f"The compiler profile field {field} contains duplicates.",
            status_code=409,
        )
    return value


def load_compiler_profile(reference: dict[str, Any]) -> LoadedCompilerProfile:
    """Load one checked-in profile and verify the exact name/version/digest pin."""

    if not isinstance(reference, dict):
        raise ServiceError(
            "compiler_profile_missing",
            "The project has no pinned compiler profile.",
            status_code=409,
        )
    try:
        project_profile = CompilerProfile.model_validate(reference)
    except ValidationError as error:
        raise ServiceError(
            "compiler_profile_invalid",
            "The project compiler profile violates its versioned contract.",
            details={"errors": error.errors(include_url=False)},
            status_code=409,
        ) from error
    project_value = project_profile.model_dump(mode="json", exclude_none=True)
    name = project_profile.name
    version = project_profile.version
    relative_path = project_profile.path
    if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise ServiceError(
            "compiler_profile_invalid",
            "The compiler profile path must stay inside the checked-in data directory.",
            status_code=409,
        )
    path = (get_settings().data_root / relative_path).resolve()
    data_root = get_settings().data_root.resolve()
    if data_root not in path.parents or not path.is_file():
        raise ServiceError(
            "compiler_profile_unknown",
            "The pinned compiler profile is not available.",
            details={"name": name, "version": version},
            status_code=409,
        )
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ServiceError(
            "compiler_profile_invalid",
            "The pinned compiler profile is not valid JSON.",
            status_code=409,
        ) from error
    if not isinstance(value, dict):
        raise ServiceError(
            "compiler_profile_invalid",
            "The pinned compiler profile must be a JSON object.",
            status_code=409,
        )
    if value.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ServiceError(
            "compiler_profile_unsupported",
            "The pinned compiler profile schema is not supported.",
            status_code=409,
        )
    if value.get("name") != name or value.get("version") != version:
        raise ServiceError(
            "compiler_profile_mismatch",
            "The compiler profile pin does not match the checked-in profile.",
            status_code=409,
        )
    if project_profile.schema_version != "1.1":
        raise ServiceError(
            "compiler_profile_upgrade_required",
            "Compilation requires a 1.1 project profile with an exact digest and agent/scope contract.",
            status_code=409,
        )
    canonical_digest = bytes_hash(canonical_json_bytes(value))
    expected_digest = project_profile.sha256
    if expected_digest != canonical_digest:
        raise ServiceError(
            "compiler_profile_digest_mismatch",
            "The compiler profile digest does not match the pinned project input.",
            status_code=409,
        )
    allowed_destinations = _string_list(value.get("allowed_destinations"), "allowed_destinations")
    allowed_transforms = _string_list(
        value.get("allowed_transform_kinds"), "allowed_transform_kinds"
    )
    unknown_destinations = sorted(set(allowed_destinations) - KNOWN_DESTINATIONS)
    unknown_transforms = sorted(set(allowed_transforms) - KNOWN_TRANSFORM_KINDS)
    if unknown_destinations or unknown_transforms:
        raise ServiceError(
            "compiler_profile_invalid",
            "The compiler profile declares an unknown destination or transform kind.",
            details={
                "destinations": unknown_destinations,
                "transform_kinds": unknown_transforms,
            },
            status_code=409,
        )
    category_routes = value.get("category_routes")
    enforcement_routes = value.get("enforcement_routes")
    dispositions = value.get("status_dispositions")
    if not all(
        isinstance(item, dict) for item in (category_routes, enforcement_routes, dispositions)
    ):
        raise ServiceError(
            "compiler_profile_invalid",
            "The compiler profile routing maps are required.",
            status_code=409,
        )
    for mapping_name, mapping in (
        ("category_routes", category_routes),
        ("enforcement_routes", enforcement_routes),
    ):
        assert isinstance(mapping, dict)
        expected_keys = (
            {
                "style",
                "workflow",
                "knowledge",
                "runtime_fact",
                "hard_constraint",
                "handoff",
                "quality",
            }
            if mapping_name == "category_routes"
            else {"prompt", "guard", "test_only", "human_review"}
        )
        if set(mapping) != expected_keys:
            raise ServiceError(
                "compiler_profile_invalid",
                f"The compiler profile field {mapping_name} must define every known key exactly once.",
                details={
                    "missing": sorted(expected_keys - set(mapping)),
                    "unknown": sorted(set(mapping) - expected_keys),
                },
                status_code=409,
            )
        for key, routes in mapping.items():
            values = _string_list(routes, f"{mapping_name}.{key}")
            unknown = sorted(set(values) - set(allowed_destinations))
            if unknown:
                raise ServiceError(
                    "compiler_profile_invalid",
                    "The compiler profile references an unknown destination.",
                    details={"destinations": unknown},
                    status_code=409,
                )
    if "compiler_scaffold" not in allowed_transforms:
        raise ServiceError(
            "compiler_profile_invalid",
            "The profile must identify compiler scaffold separately from source text.",
            status_code=409,
        )
    assert isinstance(dispositions, dict)
    if set(dispositions) != {
        "candidate",
        "needs_review",
        "approved",
        "rejected",
        "superseded",
    } or any(
        item not in {"routed", "blocked", "unsupported", "retired"}
        for item in dispositions.values()
    ):
        raise ServiceError(
            "compiler_profile_invalid",
            "The compiler profile must define a known disposition for every rule status.",
            status_code=409,
        )
    required_test_severities = value.get("require_test_for_severities")
    if not isinstance(required_test_severities, list) or any(
        item not in {"low", "medium", "high", "critical"} for item in required_test_severities
    ):
        raise ServiceError(
            "compiler_profile_invalid",
            "The compiler profile test-severity contract is invalid.",
            status_code=409,
        )
    if not isinstance(value.get("require_guard_for_approved_hard_constraints"), bool):
        raise ServiceError(
            "compiler_profile_invalid",
            "The compiler profile must declare its approved hard-constraint guard policy.",
            status_code=409,
        )
    return LoadedCompilerProfile(
        name=name,
        version=version,
        path=relative_path,
        digest=canonical_digest,
        value=value,
        project=project_value,
        project_digest=bytes_hash(canonical_json_bytes(project_value)),
    )
