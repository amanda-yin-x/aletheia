"""Record normalized-document digests separately from original-byte digests.

Revision ID: 0004_document_provenance
Revises: 0003_evidence_correctness
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "0004_document_provenance"
down_revision = "0003_evidence_correctness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("documents"):
        return
    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "normalized_sha256" not in columns:
        op.add_column(
            "documents",
            sa.Column("normalized_sha256", sa.String(length=64), nullable=True),
        )
    rows = bind.execute(sa.text("SELECT id, normalized_text FROM documents")).mappings()
    for row in rows:
        digest = hashlib.sha256(str(row["normalized_text"]).encode("utf-8")).hexdigest()
        bind.execute(
            sa.text(
                "UPDATE documents SET normalized_sha256 = :digest WHERE id = :id"
            ),
            {"digest": digest, "id": row["id"]},
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("documents") as batch:
            batch.alter_column(
                "normalized_sha256",
                existing_type=sa.String(length=64),
                nullable=False,
            )
    else:
        op.alter_column(
            "documents",
            "normalized_sha256",
            existing_type=sa.String(length=64),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("documents"):
        return
    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "normalized_sha256" in columns:
        op.drop_column("documents", "normalized_sha256")
