"""Create PMSP licitacoes table.

Revision ID: 202607040001
Revises: 202607030001
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202607040001"
down_revision = "202607030001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pmsp_licitacoes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=255), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("orgao", sa.String(length=500), nullable=True),
        sa.Column("modalidade", sa.String(length=120), nullable=True),
        sa.Column("numero_licitacao", sa.String(length=120), nullable=True),
        sa.Column("numero_processo", sa.String(length=120), nullable=True),
        sa.Column("numero_contrato", sa.String(length=120), nullable=True),
        sa.Column("objeto", sa.Text(), nullable=True),
        sa.Column("fornecedor", sa.String(length=500), nullable=True),
        sa.Column("fornecedor_documento", sa.String(length=40), nullable=True),
        sa.Column("valor_contrato", sa.Numeric(18, 2), nullable=True),
        sa.Column("data_assinatura", sa.Date(), nullable=True),
        sa.Column("data_publicacao", sa.Date(), nullable=True),
        sa.Column("evento", sa.String(length=120), nullable=True),
        sa.Column("retranca", sa.String(length=255), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_hash", name="uq_pmsp_licitacoes_source_hash"),
    )
    op.create_index("ix_pmsp_licitacoes_ano", "pmsp_licitacoes", ["ano"])
    op.create_index("ix_pmsp_licitacoes_orgao", "pmsp_licitacoes", ["orgao"])
    op.create_index("ix_pmsp_licitacoes_numero_processo", "pmsp_licitacoes", ["numero_processo"])
    op.create_index("ix_pmsp_licitacoes_numero_contrato", "pmsp_licitacoes", ["numero_contrato"])


def downgrade() -> None:
    op.drop_index("ix_pmsp_licitacoes_numero_contrato", table_name="pmsp_licitacoes")
    op.drop_index("ix_pmsp_licitacoes_numero_processo", table_name="pmsp_licitacoes")
    op.drop_index("ix_pmsp_licitacoes_orgao", table_name="pmsp_licitacoes")
    op.drop_index("ix_pmsp_licitacoes_ano", table_name="pmsp_licitacoes")
    op.drop_table("pmsp_licitacoes")
