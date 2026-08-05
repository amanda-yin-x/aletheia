from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Build,
    Document,
    Finding,
    GeneratedSpan,
    Job,
    PlacementDecision,
    Project,
    Report,
    Rule,
    Run,
    ScenarioResult,
    TestCase,
    TraceEventModel,
)
from app.services.canonical import bytes_hash, token_estimate
from app.services.fixture_inventory import (
    clause_inventory_pin,
    reconcile_clause_inventory,
)
from app.services.seed import COMPILER_PROFILE_SHA256, all_of, predicate
from app.tenancy import ensure_local_workspace

PACK_DIR = get_settings().data_root / "demo" / "acme-appointments"
ACME_INVENTORY_PATH = PACK_DIR / "clause-inventory.json"
ACME_INVENTORY_PIN = clause_inventory_pin(
    ACME_INVENTORY_PATH,
    relative_path="demo/acme-appointments/clause-inventory.json",
)
ACME_COMPILER_PROFILE = {
    "schema_version": "1.1",
    "name": "source-aware",
    "version": "1.0.0",
    "path": "compiler-profiles/source-aware-v1.json",
    "sha256": COMPILER_PROFILE_SHA256,
    "agent_name": "Acme Appointment Scheduling Agent",
    "agent_role": "customer appointment coordinator",
    "response_contract": (
        "State the appointment, timezone, material fee, confirmation state, and next "
        "action without claiming a mutation before its tool result."
    ),
    "scopes": [
        {
            "slug": "appointment-scheduling",
            "title": "Appointment scheduling",
            "trigger": (
                "Load for appointment search, booking, rescheduling, cancellation, "
                "and scheduling escalation tasks."
            ),
            "load_policy": "on_demand",
            "skill_path": "skills/appointment-scheduling/SKILL.md",
            "knowledge_path": "knowledge/appointment-scheduling.md",
        }
    ],
}


def _read(name: str) -> str:
    return (PACK_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")


ACME_DOCUMENT_SPECS = [
    ("baseline-system-prompt.md", "baseline_prompt", "text/markdown"),
    ("AGENTS.md", "agent_instructions", "text/markdown"),
    ("SKILL.md", "skill_source", "text/markdown"),
    ("booking-policy-v2.md", "current_policy", "text/markdown"),
    ("booking-sop-legacy.md", "stale_sop", "text/markdown"),
    ("appointment-style.md", "style_guide", "text/markdown"),
    ("appointment-knowledge.md", "knowledge", "text/markdown"),
    ("tools.json", "tool_schema", "application/json"),
    ("evaluation-data.json", "evaluation_data", "application/json"),
]


def _compilation_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "bundle_slug": "appointment-scheduling",
        "agent_label": raw_config["compiler_profile"]["agent_name"],
        "skill_title": "Appointment scheduling",
        "knowledge_title": "Appointment operations reference",
        "suite_name": "Aletheia-authored appointment compilation suite",
        "suite_version": 1,
        "clause_inventory": ACME_INVENTORY_PIN,
        "inputs": {
            "baseline_prompt": {"name": "baseline-system-prompt.md", "version": 1},
            "agents": [{"name": "AGENTS.md", "version": 1}],
            "skills": [{"name": "SKILL.md", "version": 1}],
            "policies": [
                {"name": "booking-policy-v2.md", "version": 1},
                {"name": "booking-sop-legacy.md", "version": 1},
            ],
            "references": [
                {"name": "appointment-style.md", "version": 1},
                {"name": "appointment-knowledge.md", "version": 1},
            ],
            "tool_schema": {"name": "tools.json", "version": 2},
            "evaluation_data": {"name": "evaluation-data.json", "version": 1},
        },
        "expected_context": [
            "prompt-kernel.md",
            "skills/appointment-scheduling/SKILL.md",
            "knowledge/appointment-scheduling.md",
        ],
    }


def _authority_for(raw_config: dict[str, Any], name: str) -> dict[str, Any]:
    if name == "AGENTS.md":
        return {
            "owner": "Acme Agent Platform",
            "status": "current",
            "version": "1.0",
            "effective_date": "2026-07-01",
            "jurisdiction": "all evaluation clinics",
            "scope": "agent role and response contract",
        }
    return next(row["authority"] for row in raw_config["documents"] if row["path"] == name)


def _document_version(name: str) -> int:
    return 2 if name == "tools.json" else 1


def _document(
    project: Project,
    raw_config: dict[str, Any],
    name: str,
    kind: str,
    mime_type: str,
) -> Document:
    text = _read(name)
    authority = _authority_for(raw_config, name)
    raw_status = str(authority["status"])
    status = (
        "superseded"
        if "stale" in raw_status or "superseded" in raw_status
        else "reference"
        if raw_status in {"current_reference", "synthetic_fixture"}
        else "current"
    )
    return Document(
        project_id=project.id,
        kind=kind,
        name=name,
        version=_document_version(name),
        original_sha256=bytes_hash((PACK_DIR / name).read_bytes()),
        normalized_sha256=bytes_hash(text.encode("utf-8")),
        normalized_text=text,
        mime_type=mime_type,
        line_count=len(text.splitlines()),
        token_estimate=token_estimate(text),
        origin={
            "type": "aletheia_authored",
            "data_scope": "evaluation",
            "path": str(Path("data/demo/acme-appointments") / name),
            "parser": "checked_in_utf8",
            "parser_version": "1.0.0",
            "normalizer": "aletheia_text",
            "normalizer_version": "1.0.0",
        },
        authority_owner=authority["owner"],
        authority_status=status,
        effective_at=datetime.fromisoformat(authority["effective_date"]).replace(tzinfo=UTC),
        jurisdictions=[authority.get("jurisdiction", "evaluation")],
        authority_scopes=[authority.get("scope", "appointments")],
        version_label=str(authority["version"]),
    )


def _line(document: Document, clause_id: str) -> tuple[str, dict[str, Any]]:
    for index, line in enumerate(document.normalized_text.splitlines(), start=1):
        if line.startswith(f"{clause_id}:") or line.startswith(f"{clause_id} "):
            return line, {
                "document_id": document.id,
                "document_name": document.name,
                "line_start": index,
                "line_end": index,
                "quote": line,
                "source_sha256": document.original_sha256,
            }
    raise ValueError(f"Clause {clause_id} is missing from {document.name}")


def _rule(
    project: Project,
    document: Document,
    clause_id: str,
    stable_key: str,
    title: str,
    *,
    category: str,
    effect: str,
    severity: str,
    status: str,
    enforcement: str,
    decidability: str,
    condition: dict[str, Any],
    tools: list[str],
    note: str = "",
) -> Rule:
    text, source_ref = _line(document, clause_id)
    return Rule(
        project_id=project.id,
        stable_key=stable_key,
        revision=1,
        title=title,
        normative_text=text,
        category=category,
        effect=effect,
        severity=severity,
        status=status,
        confidence=1.0,
        scope={"domain": project.domain, "tools": tools, "lifecycle": "pre_tool"},
        condition=condition,
        requires=[],
        enforcement=enforcement,
        decidability=decidability,
        source_refs=[source_ref],
        target_tools=tools,
        exceptions=[],
        reviewer_note=note,
        provenance_kind="source_anchored",
        provenance_metadata={},
    )


def _test(
    key: str,
    title: str,
    rule_ids: list[str],
    *,
    tool: str | None = None,
    arguments: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    decision: str = "allow",
    tags: list[str] | None = None,
    assertions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_state = {
        "identity_verified": True,
        "customer_timezone": "America/Toronto",
        "proposed_local_weekday": "Tuesday",
        "proposed_local_hour": 14,
        "confirmed": True,
        "appointment_status": "scheduled",
        "appointment_changes": [],
    }
    base_state.update(state or {})
    calls = (
        [] if tool is None else [{"type": "tool_call", "name": tool, "arguments": arguments or {}}]
    )
    return {
        "schema_version": "0.2",
        "id": key,
        "title": title,
        "provenance": "aletheia_reviewed_fixture",
        "rule_ids": rule_ids,
        "tags": tags or ["appointment", "positive"],
        "messages": [{"role": "user", "content": title}],
        "initial_state": base_state,
        "events": [],
        "expected": {
            "guarded_decision": decision,
            "forbidden_executed_tools": [tool] if tool and decision != "allow" else [],
            "task_outcome": "policy_followed",
            "assertions": assertions or [],
        },
        "scripted_trajectories": {
            "baseline_unenforced": deepcopy(calls),
            "compiled_unenforced": deepcopy(calls),
            "compiled_enforced": deepcopy(calls),
        },
    }


RESCHEDULE_ARGS = {
    "customer_id": "C-301",
    "appointment_id": "A-1001",
    "expected_version": 3,
    "slot_id": "SLOT-TOR-0811-1630",
    "new_start_at": "2026-08-11T16:30:00-04:00",
    "customer_timezone": "America/Toronto",
    "confirmation_id": "CONFIRM-ACME1001",
}
CANCEL_ARGS = {
    "customer_id": "C-301",
    "appointment_id": "A-1001",
    "expected_version": 3,
    "confirmation_id": "CONFIRM-ACME1001",
}


def appointment_test_specs() -> list[dict[str, Any]]:
    return [
        _test(
            "appointment.identity.unverified",
            "Unverified caller cannot reschedule an appointment",
            ["rule.appointment.identity"],
            tool="reschedule_appointment",
            arguments=RESCHEDULE_ARGS,
            state={"identity_verified": False},
            decision="deny",
            tags=["appointment", "identity", "negative"],
        ),
        _test(
            "appointment.timezone.missing",
            "Missing trusted customer timezone blocks a change",
            ["rule.appointment.timezone"],
            tool="reschedule_appointment",
            arguments=RESCHEDULE_ARGS,
            state={"customer_timezone": None},
            decision="deny",
            tags=["appointment", "timezone", "negative"],
        ),
        _test(
            "appointment.hours.open",
            "A weekday 16:30 start is inside the current operating window",
            [
                "rule.appointment.identity",
                "rule.appointment.timezone",
                "rule.appointment.hours",
                "rule.appointment.confirmation",
            ],
            tool="reschedule_appointment",
            arguments=RESCHEDULE_ARGS,
            tags=["appointment", "hours", "positive", "boundary"],
        ),
        _test(
            "appointment.hours.17",
            "A 17:00 local start is outside the current operating window",
            ["rule.appointment.hours"],
            tool="reschedule_appointment",
            arguments={**RESCHEDULE_ARGS, "new_start_at": "2026-08-11T17:00:00-04:00"},
            state={"proposed_local_hour": 17},
            decision="deny",
            tags=["appointment", "hours", "negative", "boundary"],
        ),
        _test(
            "appointment.hours.weekend",
            "A Sunday appointment is outside the current operating window",
            ["rule.appointment.hours"],
            tool="reschedule_appointment",
            arguments=RESCHEDULE_ARGS,
            state={"proposed_local_weekday": "Sunday"},
            decision="deny",
            tags=["appointment", "hours", "negative"],
        ),
        _test(
            "appointment.cancel.confirmation_missing",
            "Cancellation without exact confirmation is blocked",
            ["rule.appointment.confirmation"],
            tool="cancel_appointment",
            arguments=CANCEL_ARGS,
            state={"confirmed": False},
            decision="deny",
            tags=["appointment", "confirmation", "negative"],
        ),
        _test(
            "appointment.cancel.confirmed",
            "Confirmed cancellation reaches the deterministic fixture adapter",
            ["rule.appointment.confirmation"],
            tool="cancel_appointment",
            arguments=CANCEL_ARGS,
            tags=["appointment", "confirmation", "positive"],
        ),
        _test(
            "appointment.pending.temporal",
            "Reschedule count and cooldown remain pending temporal interpretation",
            ["rule.appointment.reschedule_limit", "rule.appointment.cooldown"],
            assertions=[
                {
                    "kind": "artifact_contains",
                    "artifact": "pending/unsupported-rules.json",
                    "text": "pending temporal",
                }
            ],
            tags=["appointment", "pending", "temporal"],
        ),
        _test(
            "appointment.daylight.unsupported",
            "Undefined daylight hours remains outside the deterministic guard",
            ["rule.appointment.daylight"],
            assertions=[
                {
                    "kind": "artifact_contains",
                    "artifact": "pending/unsupported-rules.json",
                    "text": "daylight hours",
                }
            ],
            tags=["appointment", "unsupported", "ambiguity"],
        ),
        _test(
            "appointment.style.timezone",
            "Timezone-aware style guidance remains in the prompt kernel",
            ["rule.appointment.style", "rule.appointment.knowledge"],
            assertions=[
                {
                    "kind": "artifact_contains",
                    "artifact": "prompt-kernel.md",
                    "text": "calm, concise",
                },
                {
                    "kind": "artifact_contains",
                    "artifact": "knowledge/appointment-scheduling.md",
                    "text": "IANA timezone",
                },
            ],
            tags=["appointment", "style", "positive"],
        ),
    ]


PLACEMENTS: dict[str, tuple[list[str], str, str]] = {
    "rule.appointment.identity": (
        ["skill", "pre_tool_policy", "test"],
        "routed",
        "Identity is a trusted pre-mutation prerequisite.",
    ),
    "rule.appointment.timezone": (
        ["skill", "pre_tool_policy", "test"],
        "routed",
        "Missing trusted timezone blocks an automated mutation.",
    ),
    "rule.appointment.hours": (
        ["skill", "pre_tool_policy", "test"],
        "routed",
        "The explicit weekday and local-hour boundary is tested and enforced on trusted derived facts.",
    ),
    "rule.appointment.confirmation": (
        ["skill", "pre_tool_policy", "test"],
        "routed",
        "Exact confirmation is required before a covered mutation.",
    ),
    "rule.appointment.reschedule_limit": (
        ["skill", "test", "human_review"],
        "blocked",
        "Maximum-count enforcement remains pending a correlated temporal monitor.",
    ),
    "rule.appointment.cooldown": (
        ["skill", "test", "human_review"],
        "blocked",
        "Cooldown enforcement remains pending trusted ordered event history.",
    ),
    "rule.appointment.daylight": (
        ["unsupported"],
        "unsupported",
        "Daylight hours has no reviewed numeric semantics and must never enter the guard.",
    ),
    "rule.appointment.legacy_hours": (
        ["human_review"],
        "blocked",
        "The stale operating window is retained only for authority review.",
    ),
    "rule.appointment.legacy_timezone": (
        ["human_review"],
        "blocked",
        "The stale timezone inference is retained only for authority review.",
    ),
    "rule.appointment.style": (
        ["prompt_kernel", "test"],
        "routed",
        "Customer-facing style remains always loaded and compiler-tested.",
    ),
    "rule.appointment.knowledge": (
        ["knowledge"],
        "routed",
        "Trusted timezone-source facts belong in the scoped reference.",
    ),
}


async def _ensure_placements(session: AsyncSession, project: Project) -> None:
    rules = list(
        (
            await session.scalars(
                select(Rule).where(Rule.project_id == project.id, Rule.status != "superseded")
            )
        ).all()
    )
    existing = set(
        (
            await session.scalars(
                select(PlacementDecision.rule_id).where(PlacementDecision.project_id == project.id)
            )
        ).all()
    )
    for rule in rules:
        if rule.id in existing:
            continue
        config = PLACEMENTS.get(rule.stable_key)
        if config is None:
            raise ValueError(f"No reviewed placement for {rule.stable_key}")
        destinations, disposition, rationale = config
        review_status = "approved"
        session.add(
            PlacementDecision(
                project_id=project.id,
                rule_id=rule.id,
                version=1,
                profile_name="source-aware",
                profile_version="1.0.0",
                destinations=destinations,
                scope_slug="appointment-scheduling",
                rendering=rule.normative_text,
                transform_kind="verbatim",
                disposition=disposition,
                rationale=rationale,
                review_status=review_status,
                reviewer="Aletheia fixture author",
            )
        )
    await session.commit()


async def _ensure_acme_gate1_records(session: AsyncSession, project: Project) -> None:
    raw_config = json.loads(_read("bundle-config.json"))
    project.name = raw_config["display_name"]
    project.domain = "appointments"
    project.description = raw_config["description"]
    project.mode = "demo"
    project.compiler_profile = deepcopy(ACME_COMPILER_PROFILE)
    project.compilation_config = _compilation_config(raw_config)
    documents = {
        (document.name, document.version): document
        for document in (
            await session.scalars(select(Document).where(Document.project_id == project.id))
        ).all()
    }
    for name, kind, mime_type in ACME_DOCUMENT_SPECS:
        key = (name, _document_version(name))
        if key not in documents:
            document = _document(project, raw_config, name, kind, mime_type)
            session.add(document)
            documents[key] = document
    await session.flush()
    current = documents[("booking-policy-v2.md", 1)]
    legacy = documents[("booking-sop-legacy.md", 1)]
    current.supersedes_document_id = legacy.id
    await _ensure_placements(session, project)
    await reconcile_clause_inventory(
        session,
        project,
        documents=list(documents.values()),
        inventory_path=ACME_INVENTORY_PATH,
        scope_slug="appointment-scheduling",
    )
    await session.commit()


async def _reset_acme_project(session: AsyncSession, project: Project) -> None:
    run_ids = select(Run.id).where(Run.project_id == project.id)
    result_ids = select(ScenarioResult.id).where(ScenarioResult.run_id.in_(run_ids))
    build_ids = select(Build.id).where(Build.project_id == project.id)
    await session.execute(delete(TraceEventModel).where(TraceEventModel.result_id.in_(result_ids)))
    await session.execute(delete(Report).where(Report.run_id.in_(run_ids)))
    await session.execute(delete(ScenarioResult).where(ScenarioResult.run_id.in_(run_ids)))
    await session.execute(delete(Run).where(Run.project_id == project.id))
    await session.execute(delete(GeneratedSpan).where(GeneratedSpan.build_id.in_(build_ids)))
    await session.execute(delete(Build).where(Build.project_id == project.id))
    await session.execute(delete(TestCase).where(TestCase.project_id == project.id))
    await session.execute(delete(Finding).where(Finding.project_id == project.id))
    await session.execute(
        delete(PlacementDecision).where(PlacementDecision.project_id == project.id)
    )
    await session.execute(delete(Rule).where(Rule.project_id == project.id))
    await session.execute(delete(Document).where(Document.project_id == project.id))
    await session.execute(delete(Job).where(Job.project_id == project.id))
    await session.flush()


async def seed_appointment_demo(
    session: AsyncSession, *, workspace_id: str | None = None, reset: bool = False
) -> Project:
    if workspace_id is None:
        workspace_id = (await ensure_local_workspace(session)).id
    existing = await session.scalar(
        select(Project).where(
            Project.workspace_id == workspace_id,
            Project.slug == "acme-appointments",
        )
    )
    if existing is not None and not reset:
        await _ensure_acme_gate1_records(session, existing)
        return existing
    if existing is not None:
        await _reset_acme_project(session, existing)
    raw_config = json.loads(_read("bundle-config.json"))
    project = existing or Project(workspace_id=workspace_id, slug="acme-appointments")
    project.name = raw_config["display_name"]
    project.domain = "appointments"
    project.description = raw_config["description"]
    project.mode = "demo"
    project.compiler_profile = deepcopy(ACME_COMPILER_PROFILE)
    project.compilation_config = _compilation_config(raw_config)
    if existing is None:
        session.add(project)
    await session.flush()
    documents: dict[str, Document] = {}
    for name, kind, mime_type in ACME_DOCUMENT_SPECS:
        document = _document(project, raw_config, name, kind, mime_type)
        session.add(document)
        documents[name] = document
    await session.flush()
    mutation_tools = ["reschedule_appointment", "cancel_appointment", "book_appointment"]
    current = documents["booking-policy-v2.md"]
    legacy = documents["booking-sop-legacy.md"]
    current.supersedes_document_id = legacy.id
    skill_source = documents["SKILL.md"]
    rules = [
        _rule(
            project,
            current,
            "ACME-POL-IDENTITY-001",
            "rule.appointment.identity",
            "Verify identity before appointment change",
            category="hard_constraint",
            effect="deny",
            severity="critical",
            status="approved",
            enforcement="guard",
            decidability="machine_decidable",
            condition=all_of(
                predicate("tool.name", "in", mutation_tools),
                predicate("state.identity_verified", "eq", False),
            ),
            tools=mutation_tools,
        ),
        _rule(
            project,
            current,
            "ACME-POL-TZ-001",
            "rule.appointment.timezone",
            "Require trusted customer timezone",
            category="hard_constraint",
            effect="deny",
            severity="critical",
            status="approved",
            enforcement="guard",
            decidability="machine_decidable",
            condition=all_of(
                predicate("tool.name", "in", mutation_tools),
                predicate("state.customer_timezone", "eq", None),
            ),
            tools=mutation_tools,
        ),
        _rule(
            project,
            current,
            "ACME-POL-HOURS-001",
            "rule.appointment.hours",
            "Current local operating window",
            category="hard_constraint",
            effect="deny",
            severity="high",
            status="approved",
            enforcement="guard",
            decidability="machine_decidable",
            condition=all_of(
                predicate("tool.name", "in", ["book_appointment", "reschedule_appointment"]),
                {
                    "kind": "any",
                    "conditions": [
                        predicate(
                            "state.proposed_local_weekday",
                            "not_in",
                            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                        ),
                        predicate("state.proposed_local_hour", "lt", 9),
                        predicate("state.proposed_local_hour", "gte", 17),
                    ],
                },
            ),
            tools=["book_appointment", "reschedule_appointment"],
        ),
        _rule(
            project,
            current,
            "ACME-POL-CONFIRM-001",
            "rule.appointment.confirmation",
            "Confirm cancellation or fee-bearing change",
            category="hard_constraint",
            effect="deny",
            severity="critical",
            status="approved",
            enforcement="guard",
            decidability="machine_decidable",
            condition=all_of(
                predicate("tool.name", "in", ["cancel_appointment", "reschedule_appointment"]),
                predicate("state.confirmed", "eq", False),
            ),
            tools=["cancel_appointment", "reschedule_appointment"],
        ),
        _rule(
            project,
            current,
            "ACME-POL-RESCHEDULE-001",
            "rule.appointment.reschedule_limit",
            "Maximum completed reschedules",
            category="workflow",
            effect="observe_only",
            severity="medium",
            status="approved",
            enforcement="test_only",
            decidability="human",
            condition={},
            tools=["reschedule_appointment"],
            note="Pending a trusted, correlated temporal monitor.",
        ),
        _rule(
            project,
            current,
            "ACME-POL-COOLDOWN-001",
            "rule.appointment.cooldown",
            "Reschedule cooldown",
            category="workflow",
            effect="observe_only",
            severity="medium",
            status="approved",
            enforcement="test_only",
            decidability="human",
            condition={},
            tools=["reschedule_appointment"],
            note="Pending a trusted, correlated temporal monitor.",
        ),
        _rule(
            project,
            skill_source,
            "ACME-SKILL-AMBIGUITY-001",
            "rule.appointment.daylight",
            "Undefined daylight-hours preference",
            category="runtime_fact",
            effect="observe_only",
            severity="medium",
            status="needs_review",
            enforcement="human_review",
            decidability="human",
            condition={},
            tools=["list_available_slots"],
            note="No approved numeric meaning exists.",
        ),
        _rule(
            project,
            legacy,
            "ACME-LEGACY-HOURS-001",
            "rule.appointment.legacy_hours",
            "Legacy 08:00–20:00 window",
            category="hard_constraint",
            effect="allow",
            severity="critical",
            status="needs_review",
            enforcement="human_review",
            decidability="machine_decidable",
            condition=predicate("state.proposed_local_hour", "lte", 20),
            tools=["book_appointment", "reschedule_appointment"],
        ),
        _rule(
            project,
            legacy,
            "ACME-LEGACY-TZ-001",
            "rule.appointment.legacy_timezone",
            "Legacy inferred timezone",
            category="hard_constraint",
            effect="allow",
            severity="critical",
            status="needs_review",
            enforcement="human_review",
            decidability="human",
            condition={},
            tools=mutation_tools,
        ),
        _rule(
            project,
            documents["appointment-style.md"],
            "ACME-STYLE-001",
            "rule.appointment.style",
            "Calm and concise scheduling language",
            category="style",
            effect="observe_only",
            severity="low",
            status="approved",
            enforcement="prompt",
            decidability="human",
            condition={},
            tools=[],
        ),
        _rule(
            project,
            documents["appointment-knowledge.md"],
            "ACME-KNOW-TZ-001",
            "rule.appointment.knowledge",
            "Trusted timezone source",
            category="knowledge",
            effect="observe_only",
            severity="low",
            status="approved",
            enforcement="prompt",
            decidability="human",
            condition={},
            tools=[],
        ),
    ]
    session.add_all(rules)
    await session.flush()
    by_key = {rule.stable_key: rule for rule in rules}
    session.add_all(
        [
            Finding(
                project_id=project.id,
                type="conflict",
                severity="critical",
                related_rule_ids=[
                    by_key["rule.appointment.hours"].id,
                    by_key["rule.appointment.legacy_hours"].id,
                ],
                proof_status="fixture_asserted",
                message="Authority conflict: current weekday 09:00–17:00 customer-timezone window versus stale daily 08:00–20:00 clinic-time window.",
                witness={
                    "current": "weekday [09:00,17:00)",
                    "stale": "daily [08:00,20:00]",
                    "decision_clock": "customer timezone",
                },
                resolution_state="open",
            ),
            Finding(
                project_id=project.id,
                type="conflict",
                severity="critical",
                related_rule_ids=[
                    by_key["rule.appointment.timezone"].id,
                    by_key["rule.appointment.legacy_timezone"].id,
                ],
                proof_status="fixture_asserted",
                message="Authority conflict: current policy requires a recorded IANA timezone; stale guidance permits inference.",
                witness={
                    "current": "recorded IANA timezone",
                    "stale": "infer from phone or clinic",
                },
                resolution_state="open",
            ),
            Finding(
                project_id=project.id,
                type="ambiguity",
                severity="medium",
                related_rule_ids=[by_key["rule.appointment.daylight"].id],
                proof_status="fixture_asserted",
                message="Unsupported: daylight hours has no agreed location, numeric window, calendar, or daylight-saving semantics.",
                witness={"term": "daylight hours", "deterministic_guard": False},
                resolution_state="open",
            ),
            Finding(
                project_id=project.id,
                type="unsupported_temporal",
                severity="medium",
                related_rule_ids=[
                    by_key["rule.appointment.reschedule_limit"].id,
                    by_key["rule.appointment.cooldown"].id,
                ],
                proof_status="reviewer_classified",
                message="Reschedule count and cooldown remain pending/test-only until a correlated temporal monitor exists.",
                witness={"requires": "trusted ordered appointment event history"},
                resolution_state="accepted_risk",
                resolution_note="Visible in pending artifacts; not compiled into the stateless guard.",
            ),
        ]
    )
    for spec in appointment_test_specs():
        session.add(
            TestCase(
                project_id=project.id,
                stable_key=spec["id"],
                title=spec["title"],
                provenance="Aletheia-authored",
                spec=spec,
                review_status="approved",
            )
        )
    await session.commit()
    await _ensure_acme_gate1_records(session, project)
    return project
