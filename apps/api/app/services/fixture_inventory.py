from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, PlacementDecision, Project, Rule
from app.services.canonical import bytes_hash, canonical_json_bytes
from app.services.errors import ServiceError

_SAFE_KEY = re.compile(r"[^a-z0-9]+")
_CATEGORIES = {
    "style",
    "workflow",
    "knowledge",
    "runtime_fact",
    "hard_constraint",
    "handoff",
    "quality",
}
_ENFORCEMENTS = {"prompt", "guard", "test_only", "human_review"}
_STATUSES = {"candidate", "needs_review", "approved", "rejected", "superseded"}
_DESTINATIONS = {
    "prompt_kernel",
    "skill",
    "knowledge",
    "pre_tool_policy",
    "test",
    "human_review",
    "unsupported",
}
_DISPOSITIONS = {"routed", "blocked", "unsupported", "retired"}


def load_clause_inventory(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ServiceError(
            "fixture_inventory_invalid",
            "The fixture-authored clause inventory is unavailable or invalid JSON.",
            status_code=409,
        ) from error
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ServiceError(
            "fixture_inventory_invalid",
            "The fixture-authored clause inventory schema is unsupported.",
            status_code=409,
        )
    return value


def clause_inventory_pin(path: Path, *, relative_path: str) -> dict[str, str]:
    value = load_clause_inventory(path)
    return {
        "path": relative_path,
        "sha256": bytes_hash(canonical_json_bytes(value)),
    }


def _decision(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ServiceError(
            "fixture_inventory_invalid",
            f"The inventory decision for {context} must be an object.",
            status_code=409,
        )
    required = {
        "category",
        "enforcement",
        "status",
        "destinations",
        "disposition",
        "review_status",
        "rationale",
    }
    if set(value) - {"lines", *required} or not required.issubset(value):
        raise ServiceError(
            "fixture_inventory_invalid",
            f"The inventory decision for {context} has missing or unknown fields.",
            status_code=409,
        )
    destinations = value["destinations"]
    if (
        value["category"] not in _CATEGORIES
        or value["enforcement"] not in _ENFORCEMENTS
        or value["status"] not in _STATUSES
        or value["disposition"] not in _DISPOSITIONS
        or value["review_status"] not in {"approved", "needs_review"}
        or not isinstance(destinations, list)
        or not destinations
        or len(destinations) != len(set(destinations))
        or any(item not in _DESTINATIONS for item in destinations)
        or not isinstance(value["rationale"], str)
        or not value["rationale"].strip()
    ):
        raise ServiceError(
            "fixture_inventory_invalid",
            f"The inventory decision for {context} violates the placement contract.",
            status_code=409,
        )
    return {key: deepcopy(value[key]) for key in required}


def _line_list(value: Any, *, context: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in value)
        or len(value) != len(set(value))
    ):
        raise ServiceError(
            "fixture_inventory_invalid",
            f"The inventory lines for {context} must be unique positive integers.",
            status_code=409,
        )
    return value


def _stable_key(document: Document, line: int) -> str:
    slug = _SAFE_KEY.sub(".", Path(document.name).stem.casefold()).strip(".")
    return f"inventory.{slug}.line.{line:04d}"


def declared_clause_lines(
    inventory: dict[str, Any], documents: list[Document]
) -> set[tuple[str, int]]:
    documents_by_key = {(item.name, item.version): item for item in documents}
    sources = inventory.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ServiceError(
            "fixture_inventory_invalid",
            "The inventory requires at least one source declaration.",
            status_code=409,
        )
    source_keys: set[tuple[str, int]] = set()
    declared: set[tuple[str, int]] = set()
    for raw_source in sources:
        if not isinstance(raw_source, dict):
            raise ServiceError(
                "fixture_inventory_invalid",
                "Every inventory source declaration must be an object.",
                status_code=409,
            )
        name = raw_source.get("document")
        version = raw_source.get("version")
        if not isinstance(name, str) or not isinstance(version, int):
            raise ServiceError(
                "fixture_inventory_invalid",
                "Every inventory source requires a document name and version.",
                status_code=409,
            )
        source_key = (name, version)
        if source_key in source_keys:
            raise ServiceError(
                "fixture_inventory_invalid",
                "An inventory document can be declared only once.",
                details={"document": name, "version": version},
                status_code=409,
            )
        source_keys.add(source_key)
        document = documents_by_key.get(source_key)
        if document is None:
            raise ServiceError(
                "fixture_inventory_document_missing",
                "An inventoried document version is missing from the project snapshot.",
                details={"document": name, "version": version},
                status_code=409,
            )
        lines = _line_list(raw_source.get("lines"), context=f"{name}@{version}")
        _decision(raw_source.get("default"), context=f"{name}@{version}")
        overridden: set[int] = set()
        for index, raw_override in enumerate(raw_source.get("overrides", [])):
            if not isinstance(raw_override, dict):
                raise ServiceError(
                    "fixture_inventory_invalid",
                    "Every inventory override must be an object.",
                    status_code=409,
                )
            override_lines = _line_list(
                raw_override.get("lines"), context=f"{name} override {index}"
            )
            if not set(override_lines).issubset(lines) or overridden.intersection(override_lines):
                raise ServiceError(
                    "fixture_inventory_invalid",
                    "Inventory override lines must be unique members of their source declaration.",
                    status_code=409,
                )
            overridden.update(override_lines)
            _decision(raw_override, context=f"{name} override {index}")
        document_lines = document.normalized_text.splitlines()
        for line in lines:
            if line > len(document_lines) or not document_lines[line - 1].strip():
                raise ServiceError(
                    "fixture_inventory_line_invalid",
                    "An inventoried line is blank or outside its immutable document version.",
                    details={"document": name, "version": version, "line": line},
                    status_code=409,
                )
            key = (document.id, line)
            if key in declared:
                raise ServiceError(
                    "fixture_inventory_invalid",
                    "An inventoried source line is declared more than once.",
                    details={"document": name, "line": line},
                    status_code=409,
                )
            declared.add(key)
    return declared


async def reconcile_clause_inventory(
    session: AsyncSession,
    project: Project,
    *,
    documents: list[Document],
    inventory_path: Path,
    scope_slug: str,
) -> int:
    """Materialize a manually declared fixture inventory without classifying text."""

    inventory = load_clause_inventory(inventory_path)
    reviewer = inventory.get("reviewer")
    sources = inventory.get("sources")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or not isinstance(sources, list)
        or not sources
    ):
        raise ServiceError(
            "fixture_inventory_invalid",
            "The inventory requires a reviewer and at least one source declaration.",
            status_code=409,
        )
    documents_by_key = {(item.name, item.version): item for item in documents}
    rules = list((await session.scalars(select(Rule).where(Rule.project_id == project.id))).all())
    covered: dict[tuple[str, int], list[Rule]] = {}
    for rule in rules:
        for source_ref in rule.source_refs:
            if not isinstance(source_ref, dict):
                continue
            document_id = source_ref.get("document_id")
            start = source_ref.get("line_start")
            end = source_ref.get("line_end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            for line in range(start, end + 1):
                covered.setdefault((str(document_id), line), []).append(rule)

    declared: set[tuple[str, int]] = set()
    created: list[tuple[Rule, dict[str, Any]]] = []
    source_keys: set[tuple[str, int]] = set()
    for raw_source in sources:
        if not isinstance(raw_source, dict):
            raise ServiceError(
                "fixture_inventory_invalid",
                "Every inventory source declaration must be an object.",
                status_code=409,
            )
        name = raw_source.get("document")
        version = raw_source.get("version")
        if not isinstance(name, str) or not isinstance(version, int):
            raise ServiceError(
                "fixture_inventory_invalid",
                "Every inventory source requires a document name and version.",
                status_code=409,
            )
        source_key = (name, version)
        if source_key in source_keys:
            raise ServiceError(
                "fixture_inventory_invalid",
                "An inventory document can be declared only once.",
                details={"document": name, "version": version},
                status_code=409,
            )
        source_keys.add(source_key)
        document = documents_by_key.get(source_key)
        if document is None:
            raise ServiceError(
                "fixture_inventory_document_missing",
                "An inventoried document version is missing from the fixture snapshot.",
                details={"document": name, "version": version},
                status_code=409,
            )
        lines = _line_list(raw_source.get("lines"), context=f"{name}@{version}")
        default = _decision(raw_source.get("default"), context=f"{name}@{version}")
        decisions = {line: default for line in lines}
        overridden: set[int] = set()
        for index, raw_override in enumerate(raw_source.get("overrides", [])):
            if not isinstance(raw_override, dict):
                raise ServiceError(
                    "fixture_inventory_invalid",
                    "Every inventory override must be an object.",
                    status_code=409,
                )
            override_lines = _line_list(
                raw_override.get("lines"), context=f"{name} override {index}"
            )
            if not set(override_lines).issubset(lines) or overridden.intersection(override_lines):
                raise ServiceError(
                    "fixture_inventory_invalid",
                    "Inventory override lines must be unique members of their source declaration.",
                    status_code=409,
                )
            overridden.update(override_lines)
            decision = _decision(raw_override, context=f"{name} override {index}")
            for line in override_lines:
                decisions[line] = decision
        document_lines = document.normalized_text.splitlines()
        for line in lines:
            if line > len(document_lines) or not document_lines[line - 1].strip():
                raise ServiceError(
                    "fixture_inventory_line_invalid",
                    "An inventoried line is blank or outside its immutable document version.",
                    details={"document": name, "version": version, "line": line},
                    status_code=409,
                )
            declaration_key = (document.id, line)
            if declaration_key in declared:
                raise ServiceError(
                    "fixture_inventory_invalid",
                    "An inventoried source line is declared more than once.",
                    details={"document": name, "line": line},
                    status_code=409,
                )
            declared.add(declaration_key)
            existing = covered.get(declaration_key, [])
            latest_by_key = {
                item.stable_key: item for item in sorted(existing, key=lambda item: item.revision)
            }
            if len(latest_by_key) > 1:
                raise ServiceError(
                    "fixture_inventory_clause_duplicate",
                    "An inventoried source line is covered by multiple rule identities.",
                    details={
                        "document": name,
                        "line": line,
                        "rules": sorted(latest_by_key),
                    },
                    status_code=409,
                )
            if latest_by_key:
                continue
            text = document_lines[line - 1]
            decision = decisions[line]
            rule = Rule(
                project_id=project.id,
                stable_key=_stable_key(document, line),
                revision=1,
                title=text[:200],
                normative_text=text,
                category=decision["category"],
                effect="observe_only",
                severity="low",
                status=decision["status"],
                confidence=1.0,
                scope={
                    "domain": project.domain,
                    "tools": [],
                    "lifecycle": "conversation",
                },
                condition={},
                requires=[],
                enforcement=decision["enforcement"],
                decidability="human",
                source_refs=[
                    {
                        "document_id": document.id,
                        "document_name": document.name,
                        "line_start": line,
                        "line_end": line,
                        "quote": text,
                        "source_sha256": document.original_sha256,
                    }
                ],
                target_tools=[],
                exceptions=[],
                reviewer_note=("Fixture-authored clause inventory; no automated classification."),
                provenance_kind="source_anchored",
                provenance_metadata={},
            )
            session.add(rule)
            created.append((rule, decision))
    await session.flush()
    for rule, decision in created:
        session.add(
            PlacementDecision(
                project_id=project.id,
                rule_id=rule.id,
                version=1,
                profile_name="source-aware",
                profile_version="1.0.0",
                destinations=decision["destinations"],
                scope_slug=scope_slug,
                rendering=rule.normative_text,
                transform_kind="verbatim",
                disposition=decision["disposition"],
                rationale=decision["rationale"],
                review_status=decision["review_status"],
                reviewer=reviewer,
            )
        )
    await session.flush()
    return len(declared)
