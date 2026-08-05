from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, PlacementDecision, Project, Rule
from app.services.errors import ServiceError

SEMANTIC_FIELDS = frozenset(
    {
        "title",
        "normative_text",
        "condition",
        "effect",
        "scope",
        "requires",
        "exceptions",
        "enforcement",
        "decidability",
        "target_tools",
    }
)


async def latest_rule(session: AsyncSession, rule_id: str) -> Rule:
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise ServiceError("rule_not_found", "Rule not found.", status_code=404)
    latest_revision = await session.scalar(
        select(func.max(Rule.revision)).where(
            Rule.project_id == rule.project_id, Rule.stable_key == rule.stable_key
        )
    )
    if latest_revision != rule.revision:
        newest = await session.scalar(
            select(Rule).where(
                Rule.project_id == rule.project_id,
                Rule.stable_key == rule.stable_key,
                Rule.revision == latest_revision,
            )
        )
        if newest:
            return newest
    return rule


async def revise_rule(
    session: AsyncSession,
    rule_id: str,
    *,
    expected_revision: int,
    changes: dict[str, Any],
    status: str | None = None,
) -> Rule:
    seed = await session.get(Rule, rule_id)
    if seed is None:
        raise ServiceError("rule_not_found", "Rule not found.", status_code=404)
    await session.scalar(select(Project).where(Project.id == seed.project_id).with_for_update())
    current = await latest_rule(session, rule_id)
    if current.revision != expected_revision:
        raise ServiceError(
            "revision_conflict",
            "This rule changed after you opened it. Refresh and review the latest revision.",
            details={
                "expected_revision": expected_revision,
                "current_revision": current.revision,
                "current_rule_id": current.id,
            },
            status_code=409,
        )
    semantic_change = any(
        key in SEMANTIC_FIELDS and value is not None and value != getattr(current, key)
        for key, value in changes.items()
    )
    fields = {
        "project_id": current.project_id,
        "stable_key": current.stable_key,
        "revision": current.revision + 1,
        "title": current.title,
        "normative_text": current.normative_text,
        "category": current.category,
        "effect": current.effect,
        "severity": current.severity,
        # A semantic change always creates a revision that must be reviewed in a
        # separate transition; callers cannot approve their own edit atomically.
        "status": "needs_review" if semantic_change else (status or current.status),
        "confidence": current.confidence,
        "scope": current.scope,
        "condition": current.condition,
        "requires": current.requires,
        "enforcement": current.enforcement,
        "decidability": current.decidability,
        "source_refs": current.source_refs,
        "target_tools": current.target_tools,
        "exceptions": current.exceptions,
        "reviewer_note": current.reviewer_note,
        "provenance_kind": current.provenance_kind,
        "provenance_metadata": current.provenance_metadata,
        "updated_at": datetime.now(UTC),
    }
    for key, value in changes.items():
        if value is not None and key in fields:
            fields[key] = value
    current.status = "superseded"
    revised = Rule(**fields)
    session.add(revised)
    await session.flush()
    current_placement = await session.scalar(
        select(PlacementDecision)
        .where(PlacementDecision.rule_id == current.id)
        .order_by(PlacementDecision.version.desc())
    )
    if current_placement is not None:
        next_disposition = current_placement.disposition
        next_review_status = current_placement.review_status
        if semantic_change:
            next_disposition = "blocked"
            next_review_status = "needs_review"
        elif status == "approved":
            next_review_status = "approved"
            if current_placement.destinations == ["unsupported"]:
                next_disposition = "unsupported"
            elif current_placement.destinations == ["human_review"]:
                next_disposition = "blocked"
            else:
                next_disposition = "routed"
        elif status == "rejected":
            next_disposition = "retired"
            next_review_status = "approved"
        next_rendering = (
            str(fields["normative_text"])
            if semantic_change and fields["normative_text"] != current.normative_text
            else current_placement.rendering
        )
        next_transform = current_placement.transform_kind
        if next_rendering != current.normative_text:
            next_transform = "reviewed_normalization"
        session.add(
            PlacementDecision(
                project_id=current.project_id,
                rule_id=revised.id,
                version=1,
                profile_name=current_placement.profile_name,
                profile_version=current_placement.profile_version,
                destinations=current_placement.destinations,
                scope_slug=current_placement.scope_slug,
                rendering=next_rendering,
                transform_kind=next_transform,
                disposition=next_disposition,
                rationale=(
                    "Placement copied from the prior revision; semantic changes require renewed review."
                    if semantic_change
                    else current_placement.rationale
                ),
                review_status=next_review_status,
                reviewer=current_placement.reviewer,
            )
        )
    await session.commit()
    await session.refresh(revised)
    return revised


async def resolve_finding(
    session: AsyncSession,
    finding_id: str,
    state: str,
    note: str,
    *,
    expected_state: str = "open",
    winner_rule_id: str | None = None,
    loser_rule_id: str | None = None,
    authority: str | None = None,
    actor: str = "system",
) -> Finding:
    seed_finding = await session.get(Finding, finding_id)
    if seed_finding is None:
        raise ServiceError("finding_not_found", "Finding not found.", status_code=404)
    await session.scalar(
        select(Project).where(Project.id == seed_finding.project_id).with_for_update()
    )
    finding = await session.scalar(
        select(Finding).where(Finding.id == finding_id).with_for_update()
    )
    if not finding:
        raise ServiceError("finding_not_found", "Finding not found.", status_code=404)
    if finding.resolution_state != expected_state:
        raise ServiceError(
            "finding_state_conflict",
            "This finding changed after you opened it. Refresh before deciding again.",
            details={
                "expected_resolution_state": expected_state,
                "current_resolution_state": finding.resolution_state,
            },
            status_code=409,
        )
    if state == "resolved":
        if not winner_rule_id or not loser_rule_id or not authority or not note.strip():
            raise ServiceError(
                "resolution_decision_required",
                "Winner, loser, authority, and rationale are required.",
            )
        if winner_rule_id == loser_rule_id:
            raise ServiceError(
                "invalid_resolution_rules",
                "Winner and loser must be different rule revisions.",
            )
        related = set(finding.related_rule_ids)
        if winner_rule_id not in related or loser_rule_id not in related:
            raise ServiceError(
                "invalid_resolution_rules",
                "Winner and loser must be revisions attached to this finding.",
            )
        rules = {
            rule.id: rule
            for rule in (
                await session.scalars(
                    select(Rule).where(
                        Rule.id.in_([winner_rule_id, loser_rule_id]),
                        Rule.project_id == finding.project_id,
                    )
                )
            ).all()
        }
        if set(rules) != {winner_rule_id, loser_rule_id}:
            raise ServiceError(
                "invalid_resolution_rules",
                "Winner and loser must belong to the finding's project.",
            )
        winner = rules[winner_rule_id]
        loser = rules[loser_rule_id]
        if winner.status in {"rejected", "superseded"}:
            raise ServiceError(
                "invalid_resolution_winner",
                "The selected winner is not an active rule revision.",
                status_code=409,
            )
        loser_placement = await session.scalar(
            select(PlacementDecision)
            .where(PlacementDecision.rule_id == loser.id)
            .order_by(PlacementDecision.version.desc())
        )
        if loser_placement is not None:
            session.add(
                PlacementDecision(
                    project_id=loser.project_id,
                    rule_id=loser.id,
                    version=loser_placement.version + 1,
                    profile_name=loser_placement.profile_name,
                    profile_version=loser_placement.profile_version,
                    destinations=["human_review"],
                    scope_slug=loser_placement.scope_slug,
                    rendering=loser.normative_text,
                    transform_kind=loser_placement.transform_kind,
                    disposition="retired",
                    rationale=(f"Retired by reviewed authority resolution: {note.strip()}"),
                    review_status="approved",
                    reviewer=actor,
                )
            )
        loser.status = "superseded"
        loser.updated_at = datetime.now(UTC)
        finding.witness = {
            **finding.witness,
            "resolution": {
                "winner_rule_id": winner_rule_id,
                "winner_revision": winner.revision,
                "loser_rule_id": loser_rule_id,
                "loser_revision": loser.revision,
                "authority": authority,
                "rationale": note.strip(),
                "actor": actor,
            },
        }
    finding.resolution_state = state
    finding.resolution_note = note.strip()
    await session.commit()
    await session.refresh(finding)
    return finding
