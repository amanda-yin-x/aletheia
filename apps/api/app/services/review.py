from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, Rule
from app.services.errors import ServiceError

SEMANTIC_FIELDS = frozenset(
    {
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
    latest_revision = await session.scalar(select(func.max(Rule.revision)).where(Rule.project_id == rule.project_id, Rule.stable_key == rule.stable_key))
    if latest_revision != rule.revision:
        newest = await session.scalar(select(Rule).where(Rule.project_id == rule.project_id, Rule.stable_key == rule.stable_key, Rule.revision == latest_revision))
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
    current = await latest_rule(session, rule_id)
    if current.revision != expected_revision:
        raise ServiceError(
            "revision_conflict",
            "This rule changed after you opened it. Refresh and review the latest revision.",
            details={"expected_revision": expected_revision, "current_revision": current.revision, "current_rule_id": current.id},
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
        "updated_at": datetime.now(UTC),
    }
    for key, value in changes.items():
        if value is not None and key in fields:
            fields[key] = value
    current.status = "superseded"
    revised = Rule(**fields)
    session.add(revised)
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
