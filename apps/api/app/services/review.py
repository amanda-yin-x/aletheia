from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, Rule
from app.services.errors import ServiceError


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
    fields = {
        "project_id": current.project_id,
        "stable_key": current.stable_key,
        "revision": current.revision + 1,
        "title": current.title,
        "normative_text": current.normative_text,
        "category": current.category,
        "effect": current.effect,
        "severity": current.severity,
        "status": status or current.status,
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


async def resolve_finding(session: AsyncSession, finding_id: str, state: str, note: str) -> Finding:
    finding = await session.get(Finding, finding_id)
    if not finding:
        raise ServiceError("finding_not_found", "Finding not found.", status_code=404)
    finding.resolution_state = state
    finding.resolution_note = note
    await session.commit()
    await session.refresh(finding)
    return finding

