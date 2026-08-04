from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, Rule
from app.services.errors import ServiceError
from app.services.review import resolve_finding, revise_rule


async def test_semantic_edit_always_requires_a_separate_reapproval(
    session: AsyncSession,
) -> None:
    current = await session.scalar(
        select(Rule).where(Rule.stable_key == "rule.refund.destination")
    )
    assert current and current.status == "approved"

    revised = await revise_rule(
        session,
        current.id,
        expected_revision=current.revision,
        changes={
            "normative_text": (
                "Refunds must return to the original payment method unless a "
                "reviewed exception applies."
            )
        },
        status="approved",
    )

    assert revised.status == "needs_review"
    assert revised.revision == current.revision + 1
    await session.refresh(current)
    assert current.status == "superseded"

    with pytest.raises(ServiceError) as stale:
        await revise_rule(
            session,
            current.id,
            expected_revision=current.revision,
            changes={"reviewer_note": "stale editor"},
        )
    assert stale.value.code == "revision_conflict"
    assert stale.value.status_code == 409


async def test_conflict_resolution_records_decision_and_retires_only_the_loser(
    session: AsyncSession,
) -> None:
    finding = await session.scalar(
        select(Finding).where(
            Finding.type == "conflict",
            Finding.message.contains("30 days"),
        )
    )
    assert finding
    related = list(
        (await session.scalars(select(Rule).where(Rule.id.in_(finding.related_rule_ids)))).all()
    )
    winner = next(rule for rule in related if rule.stable_key == "rule.refund.window")
    loser = next(rule for rule in related if rule.stable_key == "rule.legacy.window")

    with pytest.raises(ServiceError) as same_revision:
        await resolve_finding(
            session,
            finding.id,
            "resolved",
            "invalid same-revision decision",
            winner_rule_id=winner.id,
            loser_rule_id=winner.id,
            authority="Refund Policy v3",
        )
    assert same_revision.value.code == "invalid_resolution_rules"
    await session.refresh(finding)
    assert finding.resolution_state == "open"

    resolved = await resolve_finding(
        session,
        finding.id,
        "resolved",
        "Refund Policy v3 is the current approved authority.",
        winner_rule_id=winner.id,
        loser_rule_id=loser.id,
        authority="Refund Policy v3",
        actor="review-test-user",
    )

    assert resolved.witness["resolution"] == {
        "winner_rule_id": winner.id,
        "winner_revision": winner.revision,
        "loser_rule_id": loser.id,
        "loser_revision": loser.revision,
        "authority": "Refund Policy v3",
        "rationale": "Refund Policy v3 is the current approved authority.",
        "actor": "review-test-user",
    }
    await session.refresh(winner)
    await session.refresh(loser)
    assert winner.status != "superseded"
    assert loser.status == "superseded"

    with pytest.raises(ServiceError) as stale:
        await resolve_finding(
            session,
            resolved.id,
            "resolved",
            "duplicate decision",
            winner_rule_id=winner.id,
            loser_rule_id=winner.id,
            authority="Refund Policy v3",
        )
    # Optimistic state validation runs before a second decision can mutate rows.
    assert stale.value.code == "finding_state_conflict"
    assert stale.value.status_code == 409
