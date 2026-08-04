"""Pin scenario test identity for build-pinned run evidence.

Revision ID: 0003_evidence_correctness
Revises: 0002_tenancy_operations
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0003_evidence_correctness"
down_revision: str | None = "0002_tenancy_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _digest(value: Any) -> str:
    payload = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def upgrade() -> None:
    if "scenario_results" not in sa.inspect(op.get_bind()).get_table_names():
        # Some pre-release local databases were stamped at 0001 while containing
        # only the small project/build/jobs subset.  There are no results to
        # backfill in that unsupported partial snapshot.
        return
    with op.batch_alter_table("scenario_results") as batch:
        batch.add_column(sa.Column("test_snapshot", sa.JSON(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT sr.id AS result_id, tc.stable_key, tc.title, tc.provenance, tc.spec "
            "FROM scenario_results sr "
            "JOIN test_cases tc ON tc.id = sr.test_case_id"
        )
    ).mappings()
    results = sa.table(
        "scenario_results",
        sa.column("id", sa.String(36)),
        sa.column("test_snapshot", sa.JSON()),
    )
    for row in rows:
        spec = row["spec"]
        if isinstance(spec, str):
            spec = json.loads(spec)
        snapshot = {
            "stable_key": row["stable_key"],
            "title": row["title"],
            "rule_ids": spec.get("rule_ids", []),
            "tags": spec.get("tags", []),
            "provenance": row["provenance"],
            "spec_digest": _digest(spec),
        }
        bind.execute(
            results.update()
            .where(results.c.id == row["result_id"])
            .values(test_snapshot=snapshot)
        )

    with op.batch_alter_table("scenario_results") as batch:
        batch.alter_column(
            "test_snapshot", existing_type=sa.JSON(), nullable=False
        )


def downgrade() -> None:
    if "scenario_results" not in sa.inspect(op.get_bind()).get_table_names():
        return
    with op.batch_alter_table("scenario_results") as batch:
        batch.drop_column("test_snapshot")
