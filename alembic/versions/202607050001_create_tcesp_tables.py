"""Create TCE-SP transparency tables.

Revision ID: 202607050001
Revises: 202607040001
Create Date: 2026-07-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202607050001"
down_revision = "202607040001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tcesp_municipios",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("municipio_slug", sa.String(length=160), nullable=False),
        sa.Column("municipio_extenso", sa.String(length=255), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("municipio_slug", name="uq_tcesp_municipios_slug"),
    )
    op.create_index("ix_tcesp_municipios_extenso", "tcesp_municipios", ["municipio_extenso"])

    op.create_table(
        "tcesp_despesas",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("municipio_slug", sa.String(length=160), nullable=False),
        sa.Column("municipio_extenso", sa.String(length=255), nullable=True),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("mes_numero", sa.Integer(), nullable=False),
        sa.Column("mes_nome", sa.String(length=40), nullable=True),
        sa.Column("orgao", sa.String(length=500), nullable=True),
        sa.Column("evento", sa.String(length=120), nullable=True),
        sa.Column("nr_empenho", sa.String(length=120), nullable=True),
        sa.Column("id_fornecedor", sa.String(length=255), nullable=True),
        sa.Column("nm_fornecedor", sa.String(length=500), nullable=True),
        sa.Column("dt_emissao_despesa", sa.Date(), nullable=True),
        sa.Column("vl_despesa", sa.Numeric(18, 2), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(length=80), nullable=False, server_default=sa.text("'tcesp'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tcesp_despesas_municipio_periodo", "tcesp_despesas", ["municipio_slug", "exercicio", "mes_numero"])
    op.create_index("ix_tcesp_despesas_fornecedor", "tcesp_despesas", ["nm_fornecedor"])
    op.create_index("ix_tcesp_despesas_orgao", "tcesp_despesas", ["orgao"])

    op.create_table(
        "tcesp_receitas",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("municipio_slug", sa.String(length=160), nullable=False),
        sa.Column("municipio_extenso", sa.String(length=255), nullable=True),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("mes_numero", sa.Integer(), nullable=False),
        sa.Column("mes_nome", sa.String(length=40), nullable=True),
        sa.Column("orgao", sa.String(length=500), nullable=True),
        sa.Column("ds_fonte_recurso", sa.String(length=500), nullable=True),
        sa.Column("ds_cd_aplicacao_fixo", sa.String(length=500), nullable=True),
        sa.Column("ds_alinea", sa.String(length=500), nullable=True),
        sa.Column("ds_subalinea", sa.Text(), nullable=True),
        sa.Column("vl_arrecadacao", sa.Numeric(18, 2), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(length=80), nullable=False, server_default=sa.text("'tcesp'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tcesp_receitas_municipio_periodo", "tcesp_receitas", ["municipio_slug", "exercicio", "mes_numero"])
    op.create_index("ix_tcesp_receitas_orgao", "tcesp_receitas", ["orgao"])
    op.create_index("ix_tcesp_receitas_fonte", "tcesp_receitas", ["ds_fonte_recurso"])


def downgrade() -> None:
    op.drop_index("ix_tcesp_receitas_fonte", table_name="tcesp_receitas")
    op.drop_index("ix_tcesp_receitas_orgao", table_name="tcesp_receitas")
    op.drop_index("ix_tcesp_receitas_municipio_periodo", table_name="tcesp_receitas")
    op.drop_table("tcesp_receitas")

    op.drop_index("ix_tcesp_despesas_orgao", table_name="tcesp_despesas")
    op.drop_index("ix_tcesp_despesas_fornecedor", table_name="tcesp_despesas")
    op.drop_index("ix_tcesp_despesas_municipio_periodo", table_name="tcesp_despesas")
    op.drop_table("tcesp_despesas")

    op.drop_index("ix_tcesp_municipios_extenso", table_name="tcesp_municipios")
    op.drop_table("tcesp_municipios")
