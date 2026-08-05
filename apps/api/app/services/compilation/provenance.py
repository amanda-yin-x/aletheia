from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.models import Document, Rule
from app.services.canonical import bytes_hash, canonical_json_bytes
from app.services.errors import ServiceError

NEGATION_PATTERN = re.compile(
    r"\b(?:no|not|never|cannot|can't|must not|do not|without|unless|except)\b",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:[$€£]\s*)?\d+(?:[.,]\d+)?(?:\s*(?:%|days?|hours?|minutes?|times?))?",
    re.IGNORECASE,
)
QUOTED_PATTERN = re.compile(r"`([^`]+)`|[\"“]([^\"”]+)[\"”]")


def _normalized_span(document: Document, line_start: int, line_end: int) -> tuple[str, int, int]:
    lines = document.normalized_text.splitlines(keepends=True)
    if line_start < 1 or line_end < line_start or line_end > len(lines):
        raise ServiceError(
            "source_anchor_invalid",
            "A source anchor line range is outside its immutable document version.",
            details={"document": document.name, "line_start": line_start, "line_end": line_end},
            status_code=409,
        )
    before = "".join(lines[: line_start - 1])
    selected_with_endings = "".join(lines[line_start - 1 : line_end])
    selected = selected_with_endings.rstrip("\r\n")
    byte_start = len(before.encode("utf-8"))
    byte_end = byte_start + len(selected.encode("utf-8"))
    return selected, byte_start, byte_end


def verify_rule_provenance(
    rule: Rule,
    documents_by_id: dict[str, Document],
    *,
    require_verified: bool,
) -> tuple[list[dict[str, Any]], str]:
    """Resolve and verify every immutable anchor used by one rule revision."""

    provenance_kind = str(getattr(rule, "provenance_kind", "source_anchored"))
    metadata = getattr(rule, "provenance_metadata", {}) or {}
    if provenance_kind == "reviewer_authored_guidance":
        reviewed_at = metadata.get("reviewed_at") if isinstance(metadata, dict) else None
        try:
            reviewed_timestamp = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            reviewed_timestamp = None
        if (
            not isinstance(metadata, dict)
            or not str(metadata.get("reviewer", "")).strip()
            or not str(metadata.get("rationale", "")).strip()
            or reviewed_timestamp is None
            or reviewed_timestamp.tzinfo is None
            or reviewed_timestamp.utcoffset() is None
        ):
            raise ServiceError(
                "reviewer_guidance_provenance_missing",
                "Reviewer-authored guidance requires a reviewer, rationale, and offset-aware review timestamp.",
                details={"rule": rule.stable_key, "revision": rule.revision},
                status_code=409,
            )
        if rule.source_refs:
            raise ServiceError(
                "reviewer_guidance_provenance_invalid",
                "Reviewer-authored guidance cannot masquerade as source-anchored text.",
                details={"rule": rule.stable_key, "revision": rule.revision},
                status_code=409,
            )
        return [], "reviewer_authored_guidance"
    if provenance_kind != "source_anchored":
        raise ServiceError(
            "rule_provenance_kind_unknown",
            "The rule uses an unsupported provenance kind.",
            details={"rule": rule.stable_key, "provenance_kind": provenance_kind},
            status_code=409,
        )
    if require_verified and not rule.source_refs:
        raise ServiceError(
            "approved_rule_provenance_missing",
            "An approved rule has no verified immutable source anchor.",
            details={"rule": rule.stable_key, "revision": rule.revision},
            status_code=409,
        )
    anchors: list[dict[str, Any]] = []
    for source_ref in rule.source_refs:
        if not isinstance(source_ref, dict):
            raise ServiceError(
                "source_anchor_invalid",
                "A source anchor must be a structured record.",
                details={"rule": rule.stable_key},
                status_code=409,
            )
        document_id = str(source_ref.get("document_id", ""))
        document = documents_by_id.get(document_id)
        if document is None:
            raise ServiceError(
                "source_anchor_document_missing",
                "A rule references a document outside its project snapshot.",
                details={"rule": rule.stable_key, "document_id": document_id},
                status_code=409,
            )
        line_start = source_ref.get("line_start")
        line_end = source_ref.get("line_end")
        quote = source_ref.get("quote")
        if (
            not isinstance(line_start, int)
            or not isinstance(line_end, int)
            or not isinstance(quote, str)
            or not quote
        ):
            raise ServiceError(
                "source_anchor_invalid",
                "A source anchor requires an exact quote and integer line range.",
                details={"rule": rule.stable_key, "document": document.name},
                status_code=409,
            )
        actual, byte_start, byte_end = _normalized_span(document, line_start, line_end)
        if actual != quote:
            raise ServiceError(
                "source_anchor_quote_mismatch",
                "A source anchor quote does not match the immutable normalized document span.",
                details={"rule": rule.stable_key, "document": document.name},
                status_code=409,
            )
        legacy_hash = source_ref.get("source_sha256")
        if legacy_hash not in {document.original_sha256, document.normalized_sha256}:
            raise ServiceError(
                "source_anchor_hash_mismatch",
                "A source anchor hash does not match the immutable document version.",
                details={"rule": rule.stable_key, "document": document.name},
                status_code=409,
            )
        anchor_identity = {
            "document_name": document.name,
            "document_version": document.version,
            "normalized_sha256": document.normalized_sha256,
            "line_start": line_start,
            "line_end": line_end,
            "quote_sha256": bytes_hash(quote.encode("utf-8")),
        }
        anchors.append(
            {
                "source_anchor_id": bytes_hash(canonical_json_bytes(anchor_identity)),
                "document_key": f"{document.name}@{document.version}",
                "document_name": document.name,
                "document_version": document.version,
                "version_label": str(getattr(document, "version_label", "") or document.version),
                "authority_owner": str(getattr(document, "authority_owner", "") or "unspecified"),
                "authority_status": str(getattr(document, "authority_status", "") or "reference"),
                "line_start": line_start,
                "line_end": line_end,
                "utf8_byte_start": byte_start,
                "utf8_byte_end": byte_end,
                "quote": quote,
                "quote_sha256": anchor_identity["quote_sha256"],
                "original_sha256": document.original_sha256,
                "normalized_sha256": document.normalized_sha256,
                "parser": str(document.origin.get("parser", "unspecified")),
                "parser_version": str(document.origin.get("parser_version", "unspecified")),
                "normalizer": str(document.origin.get("normalizer", "unspecified")),
                "normalizer_version": str(document.origin.get("normalizer_version", "unspecified")),
            }
        )
    anchors.sort(
        key=lambda item: (
            item["document_name"],
            item["document_version"],
            item["line_start"],
            item["line_end"],
        )
    )
    transform_kind = (
        "verbatim"
        if any(anchor["quote"] == rule.normative_text for anchor in anchors)
        else "reviewed_normalization"
    )
    return anchors, transform_kind


def protected_literals(
    text: str,
    tool_names: list[str],
    enum_values: list[str] | None = None,
    structured_values: list[str] | None = None,
) -> list[dict[str, str]]:
    """Extract review-sensitive literals without claiming semantic equivalence."""

    values: set[tuple[str, str]] = set()
    for match in NEGATION_PATTERN.finditer(text):
        values.add(("negation", match.group(0)))
    for match in NUMBER_PATTERN.finditer(text):
        values.add(("threshold_or_duration", match.group(0)))
    for match in QUOTED_PATTERN.finditer(text):
        literal = match.group(1) or match.group(2)
        if literal:
            values.add(("quoted_literal", literal))
    for name in tool_names:
        if name:
            values.add(("tool_name", name))
    for value in enum_values or []:
        if value:
            values.add(("enum_value", value))
    for value in structured_values or []:
        if value:
            values.add(("structured_literal", value))
    for marker in ("unless", "except", "only", "before", "after", "above", "below"):
        if re.search(rf"\b{re.escape(marker)}\b", text, re.IGNORECASE):
            values.add(("boundary_or_exception", marker))
    return [
        {"kind": kind, "value": value}
        for kind, value in sorted(values, key=lambda item: (item[0], item[1].casefold()))
    ]
