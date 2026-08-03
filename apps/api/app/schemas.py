from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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
    conditions: list["Condition"]


class AnyCondition(APIModel):
    kind: Literal["any"] = "any"
    conditions: list["Condition"]


class NotCondition(APIModel):
    kind: Literal["not"] = "not"
    condition: "Condition"


Condition = Predicate | AllCondition | AnyCondition | NotCondition


class RuleIR(APIModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    stable_key: str
    revision: int = Field(ge=1)
    title: str
    normative_text: str
    category: Literal["style", "workflow", "knowledge", "runtime_fact", "hard_constraint", "handoff", "quality"]
    effect: Literal["allow", "deny", "require_approval", "require_prior_event", "observe_only"]
    severity: Literal["low", "medium", "high", "critical"]
    status: Literal["candidate", "needs_review", "approved", "rejected", "superseded"]
    confidence: float = Field(ge=0, le=1)
    scope: dict[str, Any]
    when: Condition | dict[str, Any]
    requires: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    enforcement: Literal["prompt", "guard", "test_only", "human_review"]
    decidability: Literal["machine_decidable", "model_judged", "human"]
    source_refs: list[SourceRef]
    target_tools: list[str] = []
    reviewer_note: str = ""


class PolicyDecisionRequest(APIModel):
    tool: dict[str, Any]
    state: dict[str, Any] = {}
    user: dict[str, Any] = {}
    context: dict[str, Any] = {}
    events: list[dict[str, Any]] = []


class PolicyDecisionResult(APIModel):
    decision: Literal["allow", "deny", "require_approval", "require_prior_event", "indeterminate"]
    reason_code: str
    reason: str
    rule_ids: list[str]
    evaluated_facts: dict[str, Any]
    decision_hash: str


class TestCaseSpec(APIModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    title: str
    provenance: str
    rule_ids: list[str]
    tags: list[str]
    messages: list[dict[str, str]]
    initial_state: dict[str, Any]
    expected: dict[str, Any]
    scripted_trajectories: dict[str, list[dict[str, Any]]]


class TraceEvent(APIModel):
    sequence: int
    type: Literal[
        "run_started", "user_message", "assistant_message", "tool_proposed",
        "policy_evaluated", "tool_blocked", "approval_required", "tool_executed",
        "tool_result", "state_changed", "final_answer", "assertion_evaluated",
        "run_finished", "error"
    ]
    payload: dict[str, Any]
    rule_ids: list[str] = []
    duration_ms: float = 0
    timestamp: datetime | None = None


class RunManifest(APIModel):
    schema_version: Literal["0.1"] = "0.1"
    adapter: str
    model: str | None = None
    arms: list[str]
    dataset: dict[str, Any]
    build_hash: str
    runner_version: str


class BuildManifest(APIModel):
    schema_version: Literal["0.1"] = "0.1"
    compiler_version: str
    input_hashes: dict[str, str]
    rule_revisions: list[str]
    artifact_hashes: dict[str, str]
    test_ids: list[str]
    estimator: str
    limitations: list[str]


class EvidenceReport(APIModel):
    schema_version: Literal["0.1"] = "0.1"
    verdict: Literal["Changes required", "Ready for controlled pilot"]
    evidence_boundary: str
    deterministic_runtime_boundary: str
    provenance: dict[str, Any]
    hashes: dict[str, str]
    comparison_arms: list[str]
    test_count: int
    metrics: dict[str, Any]
    top_failures: list[dict[str, Any]]
    limitations: list[str]


class ProjectOut(APIModel):
    id: str
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
    category: str
    effect: str
    severity: str
    status: str
    confidence: float
    scope: dict[str, Any]
    condition: dict[str, Any]
    requires: list[dict[str, Any]]
    enforcement: str
    decidability: str
    source_refs: list[dict[str, Any]]
    target_tools: list[str]
    exceptions: list[dict[str, Any]]
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
    condition: dict[str, Any] | None = None
    enforcement: str | None = None
    reviewer_note: str | None = None


class FindingPatch(APIModel):
    resolution_state: Literal["open", "resolved", "accepted_risk"]
    resolution_note: str = ""


class BuildOut(APIModel):
    id: str
    project_id: str
    status: str
    input_manifest: dict[str, Any]
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
    spec: dict[str, Any]
    review_status: str
    created_at: datetime


class RunOut(APIModel):
    id: str
    project_id: str
    build_id: str
    requested_arms: list[str]
    adapter: str
    model: str | None
    dataset_manifest: dict[str, Any]
    status: str
    metrics: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None


class ScenarioResultOut(APIModel):
    id: str
    run_id: str
    test_case_id: str
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
    evidence: dict[str, Any]
    rendered_markdown: str
    content_hash: str
    created_at: datetime


class ErrorEnvelope(APIModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str
