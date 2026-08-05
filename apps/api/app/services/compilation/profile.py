from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.canonical import bytes_hash, canonical_json_bytes
from app.services.errors import ServiceError

PROFILE_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class LoadedCompilerProfile:
    name: str
    version: str
    path: str
    digest: str
    value: dict[str, Any]


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
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item for item in value
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
    name = _required_string(reference, "name")
    version = _required_string(reference, "version")
    relative_path = _required_string(reference, "path")
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
    canonical_digest = bytes_hash(canonical_json_bytes(value))
    expected_digest = reference.get("sha256")
    if expected_digest is not None and expected_digest != canonical_digest:
        raise ServiceError(
            "compiler_profile_digest_mismatch",
            "The compiler profile digest does not match the pinned project input.",
            status_code=409,
        )
    allowed_destinations = _string_list(
        value.get("allowed_destinations"), "allowed_destinations"
    )
    allowed_transforms = _string_list(
        value.get("allowed_transform_kinds"), "allowed_transform_kinds"
    )
    category_routes = value.get("category_routes")
    enforcement_routes = value.get("enforcement_routes")
    dispositions = value.get("status_dispositions")
    if not all(isinstance(item, dict) for item in (category_routes, enforcement_routes, dispositions)):
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
    return LoadedCompilerProfile(
        name=name,
        version=version,
        path=relative_path,
        digest=canonical_digest,
        value=value,
    )
