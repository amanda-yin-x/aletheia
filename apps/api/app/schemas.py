import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
        strict=True,
    )


SHA256_PATTERN = r"^[0-9a-f]{64}$"
SEMVER_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$"
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class SourceRef(APIModel):
    document_id: str
    document_name: str | None = None
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_lines(self) -> "SourceRef":
        if self.line_end < self.line_start:
            raise ValueError("line_end must be at or after line_start")
        return self


class CompilerScopeProfile(APIModel):
    slug: str = Field(pattern=SLUG_PATTERN, min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    trigger: str | None = Field(default=None, min_length=1, max_length=1000)
    load_policy: Literal["always", "on_demand", "never"] = "on_demand"
    skill_path: str | None = None
    knowledge_path: str | None = None


class CompilerProfile(APIModel):
    """Versioned, domain-neutral rendering profile pinned by a project."""

    schema_version: Literal["1.0", "1.1"] = "1.0"
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=SEMVER_PATTERN)
    path: str = Field(min_length=1, max_length=500)
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    agent_name: str | None = Field(default=None, max_length=240)
    agent_role: str | None = Field(default=None, max_length=2000)
    response_contract: str | None = Field(default=None, max_length=5000)
    scopes: list[CompilerScopeProfile] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_versioned_project_contract(self) -> "CompilerProfile":
        if self.schema_version == "1.1":
            if not all(
                value and value.strip()
                for value in (self.agent_name, self.agent_role, self.response_contract)
            ):
                raise ValueError(
                    "compiler profile 1.1 requires agent_name, agent_role, and response_contract"
                )
            if self.sha256 is None or not self.scopes:
                raise ValueError(
                    "compiler profile 1.1 requires an exact sha256 pin and at least one scope"
                )
            for scope in self.scopes:
                if not scope.trigger or not scope.skill_path:
                    raise ValueError("compiler profile 1.1 scopes require a trigger and skill_path")
        return self


class PinnedDocumentInput(APIModel):
    name: str = Field(min_length=1, max_length=255)
    version: int = Field(ge=1)


class ClauseInventoryPin(APIModel):
    path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("path")
    @classmethod
    def relative_inventory_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("clause inventory path must stay inside the data directory")
        return value


class CompilationInputs(APIModel):
    baseline_prompt: PinnedDocumentInput
    agents: list[PinnedDocumentInput] = Field(default_factory=list)
    skills: list[PinnedDocumentInput] = Field(default_factory=list)
    policies: list[PinnedDocumentInput] = Field(default_factory=list)
    references: list[PinnedDocumentInput] = Field(default_factory=list)
    tool_schema: PinnedDocumentInput
    evaluation_data: PinnedDocumentInput

    def all_pins(self) -> list[PinnedDocumentInput]:
        return [
            self.baseline_prompt,
            *self.agents,
            *self.skills,
            *self.policies,
            *self.references,
            self.tool_schema,
            self.evaluation_data,
        ]


class CompilationConfig(APIModel):
    """Reviewed project-specific labels and exact input selections."""

    schema_version: Literal["1.0", "1.1"] = "1.0"
    bundle_slug: str = Field(pattern=SLUG_PATTERN, min_length=1, max_length=120)
    agent_label: str = Field(min_length=1, max_length=240)
    skill_title: str = Field(min_length=1, max_length=240)
    knowledge_title: str = Field(min_length=1, max_length=240)
    suite_name: str = Field(min_length=1, max_length=240)
    suite_version: int = Field(ge=1)
    inputs: CompilationInputs
    clause_inventory: ClauseInventoryPin | None = None
    expected_context: list[str] = Field(min_length=1)

    @field_validator("expected_context")
    @classmethod
    def unique_expected_context(cls, value: list[str]) -> list[str]:
        if any(
            not path.strip() or path.startswith("/") or ".." in path.split("/") for path in value
        ):
            raise ValueError("expected context paths must be non-empty relative paths")
        if len(value) != len(set(value)):
            raise ValueError("expected context paths must be unique")
        return value

    @model_validator(mode="after")
    def validate_versioned_inputs(self) -> "CompilationConfig":
        if self.schema_version == "1.1" and (
            not self.inputs.agents or not self.inputs.skills or self.clause_inventory is None
        ):
            raise ValueError(
                "compilation configuration 1.1 requires pinned AGENTS, SKILL, and clause inventory inputs"
            )
        keys = [(item.name, item.version) for item in self.inputs.all_pins()]
        if len(keys) != len(set(keys)):
            raise ValueError("compilation input pins must be unique")
        return self


class DocumentAuthorityMetadata(APIModel):
    owner: str = Field(min_length=1, max_length=200)
    status: Literal["current", "superseded", "draft", "reference"]
    effective_at: datetime | None = None
    supersedes_document_id: str | None = None
    jurisdictions: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    version_label: str = Field(min_length=1, max_length=80)


class SourceAnchor(APIModel):
    """Immutable normalized-text anchor used by Gate 1 generated spans."""

    source_anchor_id: str = Field(pattern=SHA256_PATTERN)
    document_key: str = Field(min_length=1, max_length=400)
    document_name: str = Field(min_length=1, max_length=255)
    document_version: int = Field(ge=1)
    version_label: str = Field(min_length=1, max_length=80)
    authority_owner: str = Field(min_length=1, max_length=200)
    authority_status: Literal["current", "superseded", "draft", "reference"]
    original_sha256: str = Field(pattern=SHA256_PATTERN)
    normalized_sha256: str = Field(pattern=SHA256_PATTERN)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    utf8_byte_start: int = Field(ge=0)
    utf8_byte_end: int = Field(ge=0)
    quote: str = Field(min_length=1)
    quote_sha256: str = Field(pattern=SHA256_PATTERN)
    parser: str
    parser_version: str
    normalizer: str
    normalizer_version: str

    @model_validator(mode="after")
    def validate_ranges(self) -> "SourceAnchor":
        if self.line_end < self.line_start:
            raise ValueError("line_end must be at or after line_start")
        if self.utf8_byte_end < self.utf8_byte_start:
            raise ValueError("utf8_byte_end must be at or after utf8_byte_start")
        if self.utf8_byte_end == self.utf8_byte_start:
            raise ValueError("a non-empty source quote must occupy at least one UTF-8 byte")
        if self.document_key != f"{self.document_name}@{self.document_version}":
            raise ValueError("document_key must pin the source document name and version")
        expected_quote_sha256 = hashlib.sha256(self.quote.encode("utf-8")).hexdigest()
        if self.quote_sha256 != expected_quote_sha256:
            raise ValueError("quote_sha256 must identify the exact UTF-8 source quote")
        anchor_identity = {
            "document_name": self.document_name,
            "document_version": self.document_version,
            "normalized_sha256": self.normalized_sha256,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "quote_sha256": self.quote_sha256,
        }
        canonical_identity = (
            json.dumps(
                anchor_identity,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        expected_anchor_id = hashlib.sha256(canonical_identity).hexdigest()
        if self.source_anchor_id != expected_anchor_id:
            raise ValueError("source_anchor_id must identify the immutable anchor fields")
        return self


class PlacementDecisionContract(APIModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    rule_id: str
    version: int = Field(ge=1)
    profile_name: str = Field(min_length=1, max_length=120)
    profile_version: str = Field(pattern=SEMVER_PATTERN)
    destinations: list[
        Literal[
            "prompt_kernel",
            "skill",
            "knowledge",
            "pre_tool_policy",
            "test",
            "human_review",
            "unsupported",
        ]
    ] = Field(min_length=1)
    scope_slug: str | None = Field(default=None, pattern=SLUG_PATTERN, min_length=1, max_length=120)
    rendering: str | None = None
    transform_kind: Literal[
        "verbatim",
        "reviewed_normalization",
        "reviewer_authored_guidance",
        "compiler_scaffold",
    ]
    disposition: Literal["routed", "blocked", "unsupported", "retired"]
    rationale: str = Field(min_length=1, max_length=5000)
    review_status: Literal["approved", "needs_review"]
    reviewer: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_placement(self) -> "PlacementDecisionContract":
        if len(self.destinations) != len(set(self.destinations)):
            raise ValueError("placement destinations must be unique")
        if self.disposition == "unsupported" and "unsupported" not in self.destinations:
            raise ValueError("unsupported dispositions must include the unsupported destination")
        return self


class RuleProvenanceMetadata(APIModel):
    reviewer: str | None = Field(default=None, max_length=200)
    rationale: str | None = Field(default=None, max_length=5000)
    reviewed_at: str | None = None

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("reviewed_at must be ISO 8601") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("reviewed_at must include a UTC offset")
        return value


class RuleProvenance(APIModel):
    kind: Literal["source_anchored", "reviewer_authored_guidance"] = "source_anchored"
    metadata: RuleProvenanceMetadata = Field(default_factory=RuleProvenanceMetadata)

    @model_validator(mode="after")
    def validate_reviewer_guidance(self) -> "RuleProvenance":
        if self.kind == "reviewer_authored_guidance" and (
            not self.metadata.reviewer
            or not self.metadata.rationale
            or self.metadata.reviewed_at is None
        ):
            raise ValueError(
                "reviewer-authored guidance requires reviewer, rationale, and reviewed_at"
            )
        return self


class PlacementDecisionOut(PlacementDecisionContract):
    id: str
    created_at: datetime
    updated_at: datetime


class PlacementDecisionPatch(APIModel):
    expected_version: int = Field(ge=1)
    profile_name: str | None = Field(default=None, min_length=1, max_length=120)
    profile_version: str | None = Field(default=None, pattern=SEMVER_PATTERN)
    destinations: (
        list[
            Literal[
                "prompt_kernel",
                "skill",
                "knowledge",
                "pre_tool_policy",
                "test",
                "human_review",
                "unsupported",
            ]
        ]
        | None
    ) = Field(default=None, min_length=1)
    scope_slug: str | None = Field(default=None, pattern=SLUG_PATTERN, min_length=1, max_length=120)
    rendering: str | None = None
    transform_kind: (
        Literal[
            "verbatim",
            "reviewed_normalization",
            "reviewer_authored_guidance",
            "compiler_scaffold",
        ]
        | None
    ) = None
    disposition: Literal["routed", "blocked", "unsupported", "retired"] | None = None
    rationale: str | None = Field(default=None, min_length=1, max_length=5000)
    review_status: Literal["approved", "needs_review"] | None = None
    reviewer: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_patch(self) -> "PlacementDecisionPatch":
        changed = self.model_dump(exclude={"expected_version"}, exclude_none=True)
        if not changed:
            raise ValueError("at least one placement field must change")
        if self.destinations is not None and len(self.destinations) != len(set(self.destinations)):
            raise ValueError("placement destinations must be unique")
        return self


class GeneratedSpan(APIModel):
    artifact_path: str = Field(min_length=1, max_length=500)
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    rule_id: str | None = None
    rule_stable_key: str | None = None
    rule_revision: int | None = Field(default=None, ge=1)
    placement_decision_id: str | None = None
    placement_version: int | None = Field(default=None, ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    utf8_byte_start: int = Field(ge=0)
    utf8_byte_end: int = Field(ge=0)
    transform_kind: Literal[
        "verbatim",
        "reviewed_normalization",
        "reviewer_authored_guidance",
        "compiler_scaffold",
    ]
    text_sha256: str = Field(pattern=SHA256_PATTERN)
    source_refs: list[SourceAnchor] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_generated_span(self) -> "GeneratedSpan":
        if self.line_end < self.line_start:
            raise ValueError("line_end must be at or after line_start")
        if self.utf8_byte_end < self.utf8_byte_start:
            raise ValueError("utf8_byte_end must be at or after utf8_byte_start")
        if self.transform_kind in {"verbatim", "reviewed_normalization"} and not self.source_refs:
            raise ValueError("source-derived spans require at least one source anchor")
        if self.transform_kind == "compiler_scaffold" and self.source_refs:
            raise ValueError("compiler scaffold spans cannot claim source anchors")
        return self


class GeneratedSpanOut(GeneratedSpan):
    id: str
    build_id: str
    created_at: datetime


class PlacementRecord(APIModel):
    """Immutable placement snapshot embedded in a compiled build."""

    placement_key: str = Field(min_length=1)
    rule_key: str = Field(min_length=1)
    rule_stable_key: str = Field(min_length=1)
    rule_revision: int = Field(ge=1)
    version: int = Field(ge=1)
    profile_name: str = Field(min_length=1, max_length=120)
    profile_version: str = Field(pattern=SEMVER_PATTERN)
    destinations: list[
        Literal[
            "prompt_kernel",
            "skill",
            "knowledge",
            "pre_tool_policy",
            "test",
            "human_review",
            "unsupported",
        ]
    ] = Field(min_length=1)
    scope_slug: str | None = Field(default=None, pattern=SLUG_PATTERN, min_length=1, max_length=120)
    rendering: str | None = None
    transform_kind: Literal[
        "verbatim",
        "reviewed_normalization",
        "reviewer_authored_guidance",
        "compiler_scaffold",
    ]
    disposition: Literal["routed", "blocked", "unsupported", "retired"]
    rationale: str = Field(min_length=1, max_length=5000)
    review_status: Literal["approved", "needs_review"]
    reviewer: str = Field(min_length=1, max_length=200)

    @field_validator("destinations")
    @classmethod
    def unique_destinations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("placement destinations must be unique")
        return value

    @model_validator(mode="after")
    def validate_keys(self) -> "PlacementRecord":
        expected_rule_key = f"{self.rule_stable_key}@{self.rule_revision}"
        if self.rule_key != expected_rule_key:
            raise ValueError("rule_key must identify the stable key and revision")
        if self.placement_key != f"{expected_rule_key}:placement:{self.version}":
            raise ValueError("placement_key must identify the rule and decision version")
        return self


class RoutingReportEntry(APIModel):
    rule_key: str
    rule_stable_key: str
    rule_revision: int = Field(ge=1)
    title: str
    rule_status: Literal["candidate", "needs_review", "approved", "rejected", "superseded"]
    severity: Literal["low", "medium", "high", "critical"]
    category: Literal[
        "style",
        "workflow",
        "knowledge",
        "runtime_fact",
        "hard_constraint",
        "handoff",
        "quality",
    ]
    # Optional only so stored 1.0 reports produced before compiler 1.1 remain
    # inspectable. New builds always record this typed classification.
    decidability: Literal["machine_decidable", "model_judged", "human"] | None = None
    provenance_kind: Literal["source_anchored", "reviewer_authored_guidance"]
    provenance_metadata: RuleProvenanceMetadata = Field(default_factory=RuleProvenanceMetadata)
    verified_source_anchors: int = Field(ge=0)
    source_anchors: list[SourceAnchor]
    placement: PlacementRecord
    destinations: list[
        Literal[
            "prompt_kernel",
            "skill",
            "knowledge",
            "pre_tool_policy",
            "test",
            "human_review",
            "unsupported",
        ]
    ]
    disposition: Literal["routed", "blocked", "unsupported", "retired"]
    rationale: str


class RoutingReportCounts(APIModel):
    active: int = Field(ge=0)
    routed: int = Field(ge=0)
    blocked: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    retired: int = Field(default=0, ge=0)


class RoutingReportProfile(APIModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=SEMVER_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)


class RoutingReport(APIModel):
    schema_version: Literal["1.0"] = "1.0"
    profile: RoutingReportProfile
    entries: list[RoutingReportEntry]
    counts: RoutingReportCounts

    @model_validator(mode="after")
    def validate_counts(self) -> "RoutingReport":
        expected = {
            "active": len(self.entries),
            "routed": sum(item.disposition == "routed" for item in self.entries),
            "blocked": sum(item.disposition == "blocked" for item in self.entries),
            "unsupported": sum(item.disposition == "unsupported" for item in self.entries),
            "retired": sum(item.disposition == "retired" for item in self.entries),
        }
        if self.counts.model_dump() != expected:
            raise ValueError("routing counts must match the report entries")
        return self


class ContentSizeMetric(APIModel):
    lines: int = Field(ge=0)
    characters: int = Field(ge=0)
    utf8_bytes: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)


class ProtectedLiteral(APIModel):
    kind: Literal[
        "negation",
        "threshold_or_duration",
        "quoted_literal",
        "tool_name",
        "enum_value",
        "structured_literal",
        "boundary_or_exception",
    ]
    value: str


class PreservationCheck(APIModel):
    rule_key: str
    artifact_paths: list[str] = Field(default_factory=list)
    literals: list[ProtectedLiteral]
    missing: list[ProtectedLiteral]
    preserved: bool


class PreservationReport(APIModel):
    schema_version: Literal["1.0"] = "1.0"
    checks: list[PreservationCheck]
    behavioral_fidelity: Literal["not_measured"] = "not_measured"
    interpretation: str = Field(min_length=1)


class MetricsEstimator(APIModel):
    name: str
    version: str


class ExpectedContextMetric(ContentSizeMetric):
    artifact_paths: list[str]


class RoutingMetrics(APIModel):
    active_normative_clauses: int = Field(ge=0)
    explicit_dispositions: int = Field(ge=0)
    routing_coverage: float = Field(ge=0, le=1)
    verified_source_anchor_coverage: float = Field(ge=0, le=1)
    approved_preservation: float = Field(ge=0, le=1)
    severity_weighted_approved_preservation: float = Field(ge=0, le=1)
    high_critical_guard_and_test_placement: float = Field(ge=0, le=1)
    blocked_count: int = Field(ge=0)
    unsupported_count: int = Field(ge=0)
    retired_count: int = Field(default=0, ge=0)
    unrouted_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)


class CompilationMetrics(APIModel):
    schema_version: Literal["1.0"] = "1.0"
    estimator: MetricsEstimator
    baseline_always_loaded: ContentSizeMetric
    compiled_kernel: ContentSizeMetric
    skills: dict[str, ContentSizeMetric]
    knowledge: dict[str, ContentSizeMetric]
    machine_enforced: dict[str, ContentSizeMetric]
    total_bundle_without_manifest: ContentSizeMetric
    expected_per_task_context: ExpectedContextMetric
    routing: RoutingMetrics
    protected_literals: list[PreservationCheck]
    behavioral_fidelity: Literal["not_measured"] = "not_measured"
    interpretation: str = Field(min_length=1)


class SourceMapArtifact(APIModel):
    schema_version: Literal["1.0"] = "1.0"
    range_convention: Literal["1-based inclusive lines; 0-based half-open UTF-8 byte ranges"]
    spans: list[GeneratedSpan]


class UnsupportedRuleEntry(RoutingReportEntry):
    normative_text: str
    reason: str


class UnsupportedRulesArtifact(APIModel):
    schema_version: Literal["1.0"] = "1.0"
    rules: list[UnsupportedRuleEntry]
    interpretation: str = Field(min_length=1)


class Predicate(APIModel):
    kind: Literal["predicate"] = "predicate"
    fact: str
    op: Literal["eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "exists", "contains", "regex"]
    value: Any = None


class AllCondition(APIModel):
    kind: Literal["all"] = "all"
    conditions: list["Condition"] = Field(min_length=1)


class AnyCondition(APIModel):
    kind: Literal["any"] = "any"
    conditions: list["Condition"] = Field(min_length=1)


class NotCondition(APIModel):
    kind: Literal["not"] = "not"
    condition: "Condition"


Condition = Annotated[
    Predicate | AllCondition | AnyCondition | NotCondition,
    Field(discriminator="kind"),
]


class EmptyCondition(APIModel):
    """Explicitly validates the persisted empty condition used by human-only rules."""


class RuleScope(APIModel):
    domain: str = Field(min_length=1, max_length=120)
    tools: list[str] = Field(default_factory=list)
    lifecycle: Literal["pre_tool", "post_tool", "conversation", "offline"] = "pre_tool"


class RuleRequirement(APIModel):
    kind: Literal["prior_event", "approval", "fact"]
    event_type: str | None = None
    fact: str | None = None
    op: (
        Literal[
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
        ]
        | None
    ) = None
    value: Any = None
    match_arguments: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_requirement(self) -> "RuleRequirement":
        if self.kind in {"prior_event", "approval"} and not self.event_type:
            raise ValueError("event requirements need event_type")
        if self.kind == "fact" and (not self.fact or not self.op):
            raise ValueError("fact requirements need fact and op")
        return self


class RuleException(APIModel):
    condition: Condition
    reason: str = Field(min_length=1, max_length=1000)
    effect: Literal["allow", "not_applicable"] = "not_applicable"


class CompiledSourceRef(APIModel):
    document_name: str
    document_version: int = Field(ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1)
    source_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_lines(self) -> "CompiledSourceRef":
        if self.line_end < self.line_start:
            raise ValueError("line_end must be at or after line_start")
        return self


class RuleIR(APIModel):
    schema_version: Literal["0.2"] = "0.2"
    stable_key: str
    revision: int = Field(ge=1)
    title: str
    normative_text: str
    category: Literal[
        "style", "workflow", "knowledge", "runtime_fact", "hard_constraint", "handoff", "quality"
    ]
    effect: Literal["allow", "deny", "require_approval", "require_prior_event", "observe_only"]
    severity: Literal["low", "medium", "high", "critical"]
    status: Literal["candidate", "needs_review", "approved", "rejected", "superseded"]
    confidence: float = Field(ge=0, le=1)
    scope: RuleScope
    condition: Condition | EmptyCondition
    requires: list[RuleRequirement] = Field(default_factory=list)
    exceptions: list[RuleException] = Field(default_factory=list)
    enforcement: Literal["prompt", "guard", "test_only", "human_review"]
    decidability: Literal["machine_decidable", "model_judged", "human"]
    source_refs: list[CompiledSourceRef]
    target_tools: list[str] = Field(default_factory=list)
    reviewer_note: str = ""
    provenance_kind: Literal["source_anchored", "reviewer_authored_guidance"] = "source_anchored"
    provenance_metadata: RuleProvenanceMetadata = Field(default_factory=RuleProvenanceMetadata)

    @model_validator(mode="after")
    def validate_rule_provenance(self) -> "RuleIR":
        RuleProvenance(
            kind=self.provenance_kind,
            metadata=self.provenance_metadata,
        )
        return self


class PolicyToolCall(APIModel):
    name: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any] = Field(default_factory=dict)


class PolicyEvent(APIModel):
    type: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)


class PolicyDecisionRequest(APIModel):
    tool: PolicyToolCall
    state: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    events: list[PolicyEvent] = Field(default_factory=list)


class PolicyDecisionResult(APIModel):
    decision: Literal[
        "allow",
        "deny",
        "require_approval",
        "require_prior_event",
        "indeterminate",
        "not_applicable",
    ]
    reason_code: str
    reason: str
    rule_ids: list[str]
    evaluated_facts: dict[str, Any]
    decision_hash: str


class TestMessage(APIModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolCallStep(APIModel):
    type: Literal["tool_call"] = "tool_call"
    name: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any]


class ArtifactContainsAssertion(APIModel):
    kind: Literal["artifact_contains"] = "artifact_contains"
    artifact: str = Field(min_length=1)
    text: str = Field(min_length=1)


class FindingAssertion(APIModel):
    kind: Literal["finding"] = "finding"
    type: str = Field(min_length=1)
    related_rules: list[str] = Field(min_length=1)
    resolution_state: Literal["open", "resolved", "accepted_risk"]


class ArtifactDigestAssertion(APIModel):
    kind: Literal["artifact_digest"] = "artifact_digest"
    artifact: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)


CompilerAssertion = Annotated[
    ArtifactContainsAssertion | FindingAssertion | ArtifactDigestAssertion,
    Field(discriminator="kind"),
]


class ExpectedOutcome(APIModel):
    guarded_decision: Literal[
        "allow",
        "deny",
        "require_approval",
        "require_prior_event",
        "indeterminate",
        "not_applicable",
    ]
    forbidden_executed_tools: list[str] = Field(default_factory=list)
    task_outcome: str = Field(min_length=1)
    assertions: list[CompilerAssertion] = Field(default_factory=list)


class ScriptedTrajectories(APIModel):
    baseline_unenforced: list[ToolCallStep] = Field(default_factory=list)
    compiled_unenforced: list[ToolCallStep] = Field(default_factory=list)
    compiled_enforced: list[ToolCallStep] = Field(default_factory=list)


class TestCaseSpec(APIModel):
    schema_version: Literal["0.1", "0.2"] = "0.2"
    id: str
    title: str
    provenance: str
    rule_ids: list[str]
    tags: list[str]
    messages: list[TestMessage]
    initial_state: dict[str, Any]
    events: list[PolicyEvent] = Field(default_factory=list)
    expected: ExpectedOutcome
    scripted_trajectories: ScriptedTrajectories


class CompiledTestRecord(APIModel):
    stable_key: str
    title: str
    provenance: str
    review_status: Literal["approved", "needs_review", "rejected"]
    spec: TestCaseSpec


class RegressionSuiteDescriptor(APIModel):
    name: str
    version: str
    data_scope: str
    provenance: str


class RegressionArtifact(APIModel):
    schema_version: Literal["0.2"] = "0.2"
    suite: RegressionSuiteDescriptor
    tests: list[CompiledTestRecord]


class PolicyArtifact(APIModel):
    schema_version: Literal["0.2"] = "0.2"
    default_decision: Literal["allow", "deny", "indeterminate"]
    scope_statement: str
    rules: list[RuleIR]


class ToolJSONSchema(APIModel):
    schema_uri: str | None = Field(default=None, alias="$schema", serialization_alias="$schema")
    type: Literal["object", "string", "integer", "number", "boolean", "array"]
    properties: dict[str, "ToolJSONSchema"] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    additional_properties: bool | None = Field(
        default=None,
        alias="additionalProperties",
        serialization_alias="additionalProperties",
    )
    items: "ToolJSONSchema | None" = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    min_length: int | None = Field(
        default=None, alias="minLength", serialization_alias="minLength", ge=0
    )
    max_length: int | None = Field(
        default=None, alias="maxLength", serialization_alias="maxLength", ge=0
    )
    pattern: str | None = None
    format: str | None = None
    const: str | int | bool | None = None
    enum: list[str | int | float | bool] | None = None

    @field_validator("enum")
    @classmethod
    def unique_enum_values(
        cls, value: list[str | int | float | bool] | None
    ) -> list[str | int | float | bool] | None:
        if value is not None:
            if not value:
                raise ValueError("enum must contain at least one value")
            canonical = [json.dumps(item, sort_keys=True) for item in value]
            if len(canonical) != len(set(canonical)):
                raise ValueError("enum values must be unique")
        return value


class ToolDefinition(APIModel):
    name: str = Field(min_length=1, max_length=160)
    mutating: bool
    input_schema: ToolJSONSchema


class ToolRegistry(APIModel):
    schema_version: Literal["0.2"] = "0.2"
    schema_dialect: Literal["https://json-schema.org/draft/2020-12/schema"]
    tools: list[ToolDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_tool_names(self) -> "ToolRegistry":
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")
        return self


class Money(APIModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    minor_units: int = Field(ge=0, le=999_999_999)


class CustomerFixture(APIModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    timezone: str | None
    identity: dict[str, Any] | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be an IANA timezone") from error
        return value


class OrderFixture(APIModel):
    id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    days_since_delivery: int = Field(ge=0)
    item_id: str = Field(min_length=1)
    amount: Money
    returnable: bool
    refunded: bool
    payment_method: str = Field(min_length=1)


class AppointmentFixture(APIModel):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    customer_id: str = Field(min_length=1)
    clinic_id: str = Field(min_length=1)
    service_code: str = Field(min_length=1)
    starts_at: str
    customer_timezone: str | None
    status: str = Field(min_length=1)
    reschedule_count: int = Field(ge=0)
    last_rescheduled_at: str | None
    reschedule_fee: Money
    cancellation_fee: Money


class AvailabilityFixture(APIModel):
    slot_id: str = Field(min_length=1)
    clinic_id: str = Field(min_length=1)
    service_code: str = Field(min_length=1)
    starts_at: str
    clinic_timezone: str
    available: bool


class ConfirmationFixture(APIModel):
    id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    appointment_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    proposed_start_at: str | None
    customer_timezone: str
    fee: Money
    policy_version: str
    created_at: str
    expires_at: str
    used_at: str | None


class AppointmentEventFixture(APIModel):
    event_id: str = Field(min_length=1)
    appointment_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    occurred_at: str


class FactFixture(APIModel):
    schema_version: Literal["0.2", "1.0"] = "0.2"
    data_scope: Literal["evaluation"]
    contains_customer_records: Literal[False]
    evaluation_timestamp: str
    customers: list[CustomerFixture]
    orders: list[OrderFixture] = Field(default_factory=list)
    appointments: list[AppointmentFixture] = Field(default_factory=list)
    availability: list[AvailabilityFixture] = Field(default_factory=list)
    confirmations: list[ConfirmationFixture] = Field(default_factory=list)
    appointment_events: list[AppointmentEventFixture] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_domain_records(self) -> "FactFixture":
        if not self.orders and not self.appointments:
            raise ValueError("evaluation data requires orders or appointments")
        return self

    @field_validator("evaluation_timestamp")
    @classmethod
    def validate_evaluation_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("evaluation_timestamp must be ISO 8601") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("evaluation_timestamp must include a UTC offset")
        return value


class TraceEvent(APIModel):
    sequence: int
    type: Literal[
        "run_started",
        "user_message",
        "assistant_message",
        "tool_proposed",
        "policy_evaluated",
        "tool_blocked",
        "approval_required",
        "tool_executed",
        "tool_result",
        "state_changed",
        "final_answer",
        "assertion_evaluated",
        "run_finished",
        "error",
    ]
    payload: dict[str, Any]
    rule_ids: list[str] = Field(default_factory=list)
    duration_ms: float = 0
    timestamp: datetime | None = None


class DatasetManifest(APIModel):
    schema_version: Literal["0.3"] = "0.3"
    name: str
    version: str
    data_scope: str
    provenance: str
    test_count: int = Field(ge=0)
    tests_sha256: str = Field(pattern=SHA256_PATTERN)
    tools_sha256: str = Field(pattern=SHA256_PATTERN)
    facts_sha256: str = Field(pattern=SHA256_PATTERN)
    facts_source: str
    contains_customer_records: bool
    evaluation_timestamp: str
    build_root_sha256: str = Field(pattern=SHA256_PATTERN)
    runner_version: str
    hash: str = Field(pattern=SHA256_PATTERN)


class RunManifest(APIModel):
    schema_version: Literal["0.3"] = "0.3"
    adapter: str
    model: str | None = None
    arms: list[str]
    dataset: DatasetManifest
    build_hash: str = Field(pattern=SHA256_PATTERN)
    runner_version: str


class ManifestCompiler(APIModel):
    name: str
    version: str
    serialization: str
    token_estimator: str


class ManifestCompilerProfile(APIModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=SEMVER_PATTERN)
    path: str = Field(min_length=1, max_length=500)
    digest: str = Field(pattern=SHA256_PATTERN)
    project_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)


class ManifestPlacementInput(PlacementRecord):
    digest: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_digest(self) -> "ManifestPlacementInput":
        canonical_record = (
            json.dumps(
                self.model_dump(exclude={"digest"}),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        if self.digest != hashlib.sha256(canonical_record).hexdigest():
            raise ValueError("placement digest must identify the canonical placement record")
        return self


class ManifestRuntime(APIModel):
    adapter: str
    runner_input_version: str
    policy_schema_version: str
    domain: str
    lifecycle: Literal["pre_tool", "post_tool", "conversation", "offline"]
    arms: list[str]


class ManifestSourceInput(APIModel):
    name: str
    version: int = Field(ge=1)
    kind: str
    original_sha256: str = Field(pattern=SHA256_PATTERN)
    normalized_sha256: str = Field(pattern=SHA256_PATTERN)
    parser: str
    parser_version: str
    normalizer: str
    normalizer_version: str


class ManifestRuleInput(APIModel):
    stable_key: str
    revision: int = Field(ge=1)
    status: str
    severity: Literal["low", "medium", "high", "critical"]
    category: Literal[
        "style",
        "workflow",
        "knowledge",
        "runtime_fact",
        "hard_constraint",
        "handoff",
        "quality",
    ]
    enforcement: Literal["prompt", "guard", "test_only", "human_review"]
    provenance_kind: Literal["source_anchored", "reviewer_authored_guidance"] = "source_anchored"
    provenance_metadata: RuleProvenanceMetadata = Field(default_factory=RuleProvenanceMetadata)
    source_documents: list[str]
    digest: str = Field(pattern=SHA256_PATTERN)


class ManifestTestInput(APIModel):
    stable_key: str
    title: str
    provenance: str
    rule_ids: list[str]
    tags: list[str]
    digest: str = Field(pattern=SHA256_PATTERN)


class ManifestArtifactInput(APIModel):
    source: str
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact: str
    artifact_sha256: str = Field(pattern=SHA256_PATTERN)


class ManifestFactInput(ManifestArtifactInput):
    data_scope: str
    contains_customer_records: bool


class ManifestFinding(APIModel):
    type: str
    severity: str
    proof_status: str
    message: str
    witness: dict[str, Any]
    related_rules: list[str]
    resolution_state: Literal["open", "resolved", "accepted_risk"]
    resolution_note: str


class ManifestFindings(APIModel):
    unresolved: list[ManifestFinding]
    accepted: list[ManifestFinding]


class InputManifest(APIModel):
    schema_version: Literal["0.3", "1.0"] = "0.3"
    compiler: ManifestCompiler
    runtime: ManifestRuntime
    sources: list[ManifestSourceInput]
    rules: list[ManifestRuleInput]
    tests: list[ManifestTestInput]
    tools: ManifestArtifactInput
    facts: ManifestFactInput
    findings: ManifestFindings
    compiler_profile: ManifestCompilerProfile | None = None
    placements: list[ManifestPlacementInput] = Field(default_factory=list)
    compilation_config_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def require_gate1_inputs(self) -> "InputManifest":
        if self.schema_version == "1.0" and (
            self.compiler_profile is None or self.compilation_config_digest is None
        ):
            raise ValueError(
                "Gate 1 input manifests require compiler_profile and compilation_config_digest"
            )
        return self


class ManifestSerialization(APIModel):
    json_format: str = Field(alias="json", serialization_alias="json")
    text_and_yaml: str
    hash_algorithm: Literal["sha256"]


class ManifestArtifactRoot(APIModel):
    members: list[str]
    excluded: list[Literal["manifest.json"]]
    exclusion_reason: str


class BuildManifest(APIModel):
    schema_version: Literal["0.3", "1.0"] = "0.3"
    compiler_version: str
    serialization: ManifestSerialization
    inputs: InputManifest
    input_hash: str = Field(pattern=SHA256_PATTERN)
    artifact_hashes: dict[str, str]
    artifact_root: ManifestArtifactRoot
    unresolved_findings: list[ManifestFinding]
    accepted_findings: list[ManifestFinding]
    limitations: list[str]

    @model_validator(mode="after")
    def align_manifest_versions(self) -> "BuildManifest":
        if self.schema_version == "1.0" and self.inputs.schema_version != "1.0":
            raise ValueError("Gate 1 build manifests require Gate 1 input manifests")
        return self


class EvidenceProvenance(APIModel):
    dataset: str
    version: str
    data_scope: str
    fixture_source: str
    contains_customer_records: bool
    evaluation_timestamp: str
    test_count: int = Field(ge=0)
    dataset_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    adapter: str
    model: str
    compiler_version: str
    runner_version: str


class EvidenceSourceHash(APIModel):
    name: str
    version: int = Field(ge=1)
    original_sha256: str = Field(pattern=SHA256_PATTERN)
    normalized_sha256: str = Field(pattern=SHA256_PATTERN)
    parser: str
    parser_version: str
    normalizer: str
    normalizer_version: str


class EvidenceTestHash(APIModel):
    stable_key: str
    spec_sha256: str = Field(pattern=SHA256_PATTERN)


class EvidenceHashes(APIModel):
    build_root_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_bytes_sha256: str = Field(pattern=SHA256_PATTERN)
    run_sha256: str = Field(pattern=SHA256_PATTERN)
    test_suite_sha256: str = Field(pattern=SHA256_PATTERN)
    tool_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    fact_fixture_sha256: str = Field(pattern=SHA256_PATTERN)
    source_documents: list[EvidenceSourceHash]
    tests: list[EvidenceTestHash]
    artifacts: dict[str, str]


class FixtureTestProvenance(APIModel):
    name: str
    version: str
    provenance: str
    data_scope: str


class FixtureProvenance(APIModel):
    facts: ManifestFactInput
    tools: ManifestArtifactInput
    tests: FixtureTestProvenance


class ArmMetrics(APIModel):
    cases: int = Field(ge=0)
    task_success_rate: float = Field(ge=0, le=1)
    attempted_violation_rate: float = Field(ge=0, le=1)
    executed_violation_rate: float = Field(ge=0, le=1)
    false_block_rate: float = Field(ge=0, le=1)
    tool_validation_error_rate: float = Field(ge=0, le=1)
    input_tokens: int | None
    output_tokens: int | None
    cost: float | None


class CoverageMetrics(APIModel):
    test_count: int = Field(ge=0)
    arms: int = Field(ge=0)
    tag_counts: dict[str, int]
    positive_negative_boundary: bool
    executable_case_count: int = Field(ge=0)
    compiler_assertion_case_count: int = Field(ge=0)
    explicit_assertion_case_count: int = Field(ge=0)
    explicit_assertion_coverage: float = Field(ge=0, le=1)
    compiler_assertion_coverage: float = Field(ge=0, le=1)
    declared_rule_linkage: "CoverageDimension"
    declared_source_linkage: "CoverageDimension"
    declared_boundary_linkage: "CoverageDimension"
    critical_unclassified_rules: list[str]


class CoverageDimension(APIModel):
    eligible_count: int = Field(ge=0)
    covered_count: int = Field(ge=0)
    ratio: float = Field(ge=0, le=1)
    uncovered: list[str]


class EvidenceMetrics(APIModel):
    baseline_unenforced: ArmMetrics
    compiled_unenforced: ArmMetrics
    compiled_enforced: ArmMetrics
    coverage: CoverageMetrics


class EvidenceFailure(APIModel):
    test_id: str
    title: str
    arm: str
    first_divergence: str | None


class EvidencePayload(APIModel):
    schema_version: Literal["0.3"] = "0.3"
    verdict: Literal["Changes required", "Fixture suite passed"]
    evidence_boundary: str
    deterministic_runtime_boundary: str
    digest_definition: str
    provenance: EvidenceProvenance
    hashes: EvidenceHashes
    fixture_provenance: FixtureProvenance
    comparison_arms: list[str]
    test_count: int
    metrics: EvidenceMetrics
    top_failures: list[EvidenceFailure]
    limitations: list[str]


class EvidenceReport(EvidencePayload):
    report_digest: str = Field(pattern=SHA256_PATTERN)


class ProjectOut(APIModel):
    id: str
    workspace_id: str
    slug: str
    name: str
    domain: str
    description: str
    mode: str
    compiler_profile: CompilerProfile = Field(
        default_factory=lambda: CompilerProfile(
            name="source-aware",
            version="1.0.0",
            path="compiler-profiles/source-aware-v1.json",
        )
    )
    compilation_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentOut(APIModel):
    id: str
    project_id: str
    kind: str
    name: str
    version: int
    original_sha256: str
    normalized_sha256: str
    normalized_text: str
    mime_type: str
    line_count: int
    token_estimate: int
    origin: dict[str, Any]
    authority_owner: str = "unspecified"
    authority_status: Literal["current", "superseded", "draft", "reference"] = "reference"
    effective_at: datetime | None = None
    supersedes_document_id: str | None = None
    jurisdictions: list[str] = Field(default_factory=list)
    authority_scopes: list[str] = Field(default_factory=list)
    version_label: str = ""
    created_at: datetime


class RuleOut(APIModel):
    id: str
    project_id: str
    stable_key: str
    revision: int
    title: str
    normative_text: str
    category: Literal[
        "style",
        "workflow",
        "knowledge",
        "runtime_fact",
        "hard_constraint",
        "handoff",
        "quality",
    ]
    effect: Literal[
        "allow",
        "deny",
        "require_approval",
        "require_prior_event",
        "observe_only",
    ]
    severity: Literal["low", "medium", "high", "critical"]
    status: Literal["candidate", "needs_review", "approved", "rejected", "superseded"]
    confidence: float
    scope: RuleScope
    condition: Condition | EmptyCondition
    requires: list[RuleRequirement]
    enforcement: Literal["prompt", "guard", "test_only", "human_review"]
    decidability: Literal["machine_decidable", "model_judged", "human"]
    source_refs: list[SourceRef]
    target_tools: list[str]
    exceptions: list[RuleException]
    reviewer_note: str
    provenance_kind: Literal["source_anchored", "reviewer_authored_guidance"] = "source_anchored"
    provenance_metadata: RuleProvenanceMetadata = Field(default_factory=RuleProvenanceMetadata)
    created_at: datetime
    updated_at: datetime


class FindingOut(APIModel):
    id: str
    project_id: str
    type: str
    severity: str
    related_rule_ids: list[str]
    proof_status: str
    message: str
    witness: dict[str, Any]
    resolution_state: str
    resolution_note: str
    created_at: datetime


class RulePatch(APIModel):
    expected_revision: int
    title: str | None = None
    normative_text: str | None = None
    condition: Condition | EmptyCondition | None = None
    enforcement: Literal["prompt", "guard", "test_only", "human_review"] | None = None
    effect: (
        Literal[
            "allow",
            "deny",
            "require_approval",
            "require_prior_event",
            "observe_only",
        ]
        | None
    ) = None
    scope: RuleScope | None = None
    requires: list[RuleRequirement] | None = None
    exceptions: list[RuleException] | None = None
    decidability: Literal["machine_decidable", "model_judged", "human"] | None = None
    target_tools: list[str] | None = None
    reviewer_note: str | None = None


class FindingPatch(APIModel):
    resolution_state: Literal["open", "resolved", "accepted_risk"]
    resolution_note: str = Field(default="", max_length=5000)
    expected_resolution_state: Literal["open", "resolved", "accepted_risk"] = "open"
    winner_rule_id: str | None = None
    loser_rule_id: str | None = None
    authority: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_resolution_decision(self) -> "FindingPatch":
        if self.resolution_state == "resolved":
            if not all(
                [
                    self.winner_rule_id,
                    self.loser_rule_id,
                    self.authority,
                    self.resolution_note.strip(),
                ]
            ):
                raise ValueError(
                    "Resolved findings require winner, loser, authority, and rationale"
                )
            if self.winner_rule_id == self.loser_rule_id:
                raise ValueError("Winner and loser must be different rule revisions")
        return self


class RuleReview(APIModel):
    expected_revision: int = Field(ge=1)
    reviewer_note: str | None = Field(default=None, max_length=5000)


class TestCasePatch(APIModel):
    review_status: Literal["approved", "needs_review", "rejected"]


class RunCreate(APIModel):
    build_id: str | None = None


class BuildSizeStats(APIModel):
    lines: int = Field(ge=0)
    characters: int = Field(ge=0)
    tokens: int = Field(ge=0)


class BuildReductionStats(APIModel):
    lines: int
    characters: int
    estimated_tokens: int
    label: str = Field(min_length=1)


class BuildRoutingStats(APIModel):
    kept_in_prompt: int = Field(ge=0)
    moved_to_workflow: int = Field(ge=0)
    guarded: int = Field(ge=0)
    tested: int = Field(ge=0)


class BuildStats(APIModel):
    original: BuildSizeStats
    candidate: BuildSizeStats
    reduction: BuildReductionStats
    routing: BuildRoutingStats
    compilation: CompilationMetrics


class BuildOut(APIModel):
    id: str
    project_id: str
    status: str
    input_manifest: InputManifest
    input_hash: str
    compiler_version: str
    artifacts: dict[str, Any]
    source_map: dict[str, Any]
    stats: BuildStats | None
    content_hash: str
    created_at: datetime


class BuildArtifactInspection(APIModel):
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)


class BuildInspectionOut(APIModel):
    build_id: str
    project_id: str
    status: str
    input_hash: str = Field(pattern=SHA256_PATTERN)
    compiler_version: str
    content_hash: str = Field(pattern=SHA256_PATTERN)
    artifacts: list[BuildArtifactInspection]
    source_map: SourceMapArtifact | dict[str, list[str]]
    stats: BuildStats | None
    routing_report: RoutingReport | None
    preservation_report: PreservationReport | None
    generated_spans: list[GeneratedSpanOut]


class TestCaseOut(APIModel):
    id: str
    project_id: str
    stable_key: str
    title: str
    provenance: str
    spec: TestCaseSpec
    review_status: Literal["approved", "needs_review", "rejected"]
    created_at: datetime


class RunOut(APIModel):
    id: str
    project_id: str
    build_id: str
    requested_arms: list[str]
    adapter: str
    model: str | None
    dataset_manifest: DatasetManifest
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    metrics: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None


class ProjectSummaryOut(APIModel):
    sources: int = Field(ge=0)
    approved_rules: int = Field(ge=0)
    critical_findings: int = Field(ge=0)
    tests: int = Field(ge=0)
    current_build: BuildOut | None
    last_run: RunOut | None


class TestSnapshot(APIModel):
    stable_key: str
    title: str
    rule_ids: list[str]
    tags: list[str]
    provenance: str
    spec_digest: str = Field(pattern=SHA256_PATTERN)


class ScenarioResultOut(APIModel):
    id: str
    run_id: str
    test_case_id: str
    test_snapshot: TestSnapshot
    arm: str
    verdict: str
    metrics: dict[str, Any]
    final_state_hash: str
    first_divergence: str | None
    trace_id: str


class ReportOut(APIModel):
    id: str
    run_id: str
    verdict: str
    evidence: EvidenceReport
    rendered_markdown: str
    content_hash: str
    created_at: datetime


class ErrorEnvelope(APIModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str


class ProjectCreate(APIModel):
    workspace_id: str
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(default="retail", min_length=1, max_length=80)
    description: str = Field(default="", max_length=5000)


class WorkspaceBootstrap(APIModel):
    name: str = Field(default="My workspace", min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkspaceOut(APIModel):
    id: str
    slug: str
    name: str
    role: str
    created_at: datetime


class MeOut(APIModel):
    id: str
    email: str | None
    is_anonymous: bool
    workspaces: list[WorkspaceOut]


class WaitlistCreate(APIModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if any(character.isspace() for character in normalized):
            raise ValueError("Enter a valid email address")
        local, separator, domain = normalized.rpartition("@")
        if (
            separator != "@"
            or not local
            or len(local) > 64
            or not domain
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError("Enter a valid email address")
        try:
            ascii_domain = domain.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise ValueError("Enter a valid email address") from error
        return f"{local}@{ascii_domain}"


class WaitlistOut(APIModel):
    joined: Literal[True] = True


class WorkspaceBootstrapOut(APIModel):
    workspace: WorkspaceOut
    project: ProjectOut
    created: bool


class OperationError(APIModel):
    code: str
    message: str


class OperationOut(APIModel):
    id: str
    workspace_id: str
    kind: str
    status: Literal["queued", "running", "succeeded", "failed", "dead_lettered", "cancelled"]
    progress: int = Field(ge=0, le=100)
    resource_type: Literal["build", "run", "project"] | None
    resource_id: str | None
    attempt_count: int
    max_attempts: int
    error: OperationError | None = None
    created_at: datetime
    updated_at: datetime
