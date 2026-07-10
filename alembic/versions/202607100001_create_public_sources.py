"""Create public sources table for official publication scraping.

Revision ID: 202607100001
Revises: 202607050001
Create Date: 2026-07-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202607100001"
down_revision = "202607050001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_sources",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("normalized_url", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default=sa.text("'official_site'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=200), nullable=True),
        sa.Column("detected_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("detected_endpoints", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("normalized_url", name="uq_public_sources_normalized_url"),
    )
    op.create_index("ix_public_sources_source_id", "public_sources", ["source_id"])
    op.create_index("ix_public_sources_status", "public_sources", ["status"])
    op.create_index("ix_public_sources_last_inspected_at", "public_sources", ["last_inspected_at"])


def downgrade() -> None:
    op.drop_index("ix_public_sources_last_inspected_at", table_name="public_sources")
    op.drop_index("ix_public_sources_status", table_name="public_sources")
    op.drop_index("ix_public_sources_source_id", table_name="public_sources")
    op.drop_table("public_sources")
