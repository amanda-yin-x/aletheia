from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.canonical import bytes_hash


def _line_range(text_before: str, value: str) -> tuple[int, int]:
    line_start = text_before.count("\n") + 1
    line_end = line_start + value.count("\n")
    if value.endswith("\n") and line_end > line_start:
        line_end -= 1
    return line_start, line_end


@dataclass
class SpanWriter:
    artifact_path: str
    parts: list[str] = field(default_factory=list)
    spans: list[dict[str, Any]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def append(
        self,
        value: str,
        *,
        transform_kind: str,
        rule: Any | None = None,
        placement: Any | None = None,
        source_refs: list[dict[str, Any]] | None = None,
    ) -> None:
        if not value:
            return
        before = self.text
        byte_start = len(before.encode("utf-8"))
        byte_end = byte_start + len(value.encode("utf-8"))
        line_start, line_end = _line_range(before, value)
        self.parts.append(value)
        self.spans.append(
            {
                "artifact_path": self.artifact_path,
                "artifact_sha256": "",
                "line_start": line_start,
                "line_end": line_end,
                "utf8_byte_start": byte_start,
                "utf8_byte_end": byte_end,
                "transform_kind": transform_kind,
                "text_sha256": bytes_hash(value.encode("utf-8")),
                "rule_id": (f"{rule.stable_key}@{rule.revision}" if rule is not None else None),
                "rule_stable_key": str(getattr(rule, "stable_key", "")) or None,
                "rule_revision": getattr(rule, "revision", None),
                "placement_decision_id": (
                    f"{rule.stable_key}@{rule.revision}:placement:{placement.version}"
                    if rule is not None and placement is not None
                    else None
                ),
                "placement_version": getattr(placement, "version", None),
                "source_refs": source_refs or [],
            }
        )

    def scaffold(self, value: str) -> None:
        self.append(value, transform_kind="compiler_scaffold")

    def bullet(
        self,
        text: str,
        *,
        transform_kind: str,
        rule: Any,
        placement: Any,
        source_refs: list[dict[str, Any]],
    ) -> None:
        self.scaffold("- ")
        self.append(
            text,
            transform_kind=transform_kind,
            rule=rule,
            placement=placement,
            source_refs=source_refs,
        )
        self.scaffold("\n")

    def finish(self) -> tuple[str, list[dict[str, Any]]]:
        value = self.text
        if not value.endswith("\n"):
            self.scaffold("\n")
            value = self.text
        digest = bytes_hash(value.encode("utf-8"))
        for span in self.spans:
            span["artifact_sha256"] = digest
        return value, self.spans


def locate_fragment_span(
    artifact_path: str,
    artifact_text: str,
    fragment: str,
    *,
    transform_kind: str,
    rule: Any | None,
    placement: Any | None,
    source_refs: list[dict[str, Any]],
    start_at: int = 0,
) -> tuple[dict[str, Any], int]:
    """Map a deterministic serialized fragment to its exact UTF-8 range."""

    character_start = artifact_text.find(fragment, start_at)
    if character_start < 0:
        raise ValueError(f"serialized fragment not found in {artifact_path}")
    character_end = character_start + len(fragment)
    before = artifact_text[:character_start]
    byte_start = len(before.encode("utf-8"))
    byte_end = byte_start + len(fragment.encode("utf-8"))
    line_start, line_end = _line_range(before, fragment)
    return (
        {
            "artifact_path": artifact_path,
            "artifact_sha256": bytes_hash(artifact_text.encode("utf-8")),
            "line_start": line_start,
            "line_end": line_end,
            "utf8_byte_start": byte_start,
            "utf8_byte_end": byte_end,
            "transform_kind": transform_kind,
            "text_sha256": bytes_hash(fragment.encode("utf-8")),
            "rule_id": (f"{rule.stable_key}@{rule.revision}" if rule is not None else None),
            "rule_stable_key": str(getattr(rule, "stable_key", "")) or None,
            "rule_revision": getattr(rule, "revision", None),
            "placement_decision_id": (
                f"{rule.stable_key}@{rule.revision}:placement:{placement.version}"
                if rule is not None and placement is not None
                else None
            ),
            "placement_version": getattr(placement, "version", None),
            "source_refs": source_refs,
        },
        character_end,
    )
