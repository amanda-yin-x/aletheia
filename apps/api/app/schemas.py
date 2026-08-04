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


class Predicate(APIModel):
    kind: Literal["predicate"] = "predicate"
    fact: str
    op: Literal[
        "eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "exists", "contains", "regex"
    ]
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
    op: Literal[
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
    ] | None = None
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
    category: Literal["style", "workflow", "knowledge", "runtime_fact", "hard_constraint", "handoff", "quality"]
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
    schema_uri: str | None = Field(
        default=None, alias="$schema", serialization_alias="$schema"
    )
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


class FactFixture(APIModel):
    schema_version: Literal["0.2"] = "0.2"
    data_scope: Literal["evaluation"]
    contains_customer_records: Literal[False]
    evaluation_timestamp: str
    customers: list[CustomerFixture]
    orders: list[OrderFixture]

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
        "run_started", "user_message", "assistant_message", "tool_proposed",
        "policy_evaluated", "tool_blocked", "approval_required", "tool_executed",
        "tool_result", "state_changed", "final_answer", "assertion_evaluated",
        "run_finished", "error"
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
    schema_version: Literal["0.3"] = "0.3"
    compiler: ManifestCompiler
    runtime: ManifestRuntime
    sources: list[ManifestSourceInput]
    rules: list[ManifestRuleInput]
    tests: list[ManifestTestInput]
    tools: ManifestArtifactInput
    facts: ManifestFactInput
    findings: ManifestFindings


class ManifestSerialization(APIModel):
    json_format: str = Field(alias="json", serialization_alias="json")
    text_and_yaml: str
    hash_algorithm: Literal["sha256"]


class ManifestArtifactRoot(APIModel):
    members: list[str]
    excluded: list[Literal["manifest.json"]]
    exclusion_reason: str


class BuildManifest(APIModel):
    schema_version: Literal["0.3"] = "0.3"
    compiler_version: str
    serialization: ManifestSerialization
    inputs: InputManifest
    input_hash: str = Field(pattern=SHA256_PATTERN)
    artifact_hashes: dict[str, str]
    artifact_root: ManifestArtifactRoot
    unresolved_findings: list[ManifestFinding]
    accepted_findings: list[ManifestFinding]
    limitations: list[str]


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
    rule_coverage: "CoverageDimension"
    source_coverage: "CoverageDimension"
    boundary_coverage: "CoverageDimension"
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
    effect: Literal[
        "allow",
        "deny",
        "require_approval",
        "require_prior_event",
        "observe_only",
    ] | None = None
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


class BuildOut(APIModel):
    id: str
    project_id: str
    status: str
    input_manifest: InputManifest
    input_hash: str
    compiler_version: str
    artifacts: dict[str, Any]
    source_map: dict[str, Any]
    stats: dict[str, Any]
    content_hash: str
    created_at: datetime


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
    slug: str | None = Field(
        default=None, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )


class WorkspaceOut(APIModel):
    id: str
    slug: str
    name: str
    role: str
    created_at: datetime


class MeOut(APIModel):
    id: str
    email: str | None
    workspaces: list[WorkspaceOut]


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
