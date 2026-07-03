"""Initial HERMES schema.

Revision ID: 202607030001
Revises:
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202607030001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")

    op.create_table(
        "sources",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_name", sa.String(length=120), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("scope", sa.String(length=80), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_sources_code"),
    )

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_found", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "publications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("organization", sa.String(length=500), nullable=True),
        sa.Column("entity", sa.String(length=500), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("municipality", sa.String(length=255), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("api_name", sa.String(length=120), nullable=True),
        sa.Column("publication_type", sa.String(length=120), nullable=True),
        sa.Column("object", sa.Text(), nullable=True),
        sa.Column("modality", sa.String(length=120), nullable=True),
        sa.Column("situation", sa.String(length=120), nullable=True),
        sa.Column("number", sa.String(length=120), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("winner_company_name", sa.String(length=500), nullable=True),
        sa.Column("winner_cnpj", sa.String(length=20), nullable=True),
        sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("awarded_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("contracted_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("addendum_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("deadline", sa.String(length=255), nullable=True),
        sa.Column("validity_start", sa.Date(), nullable=True),
        sa.Column("validity_end", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("normalized_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("classification", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("keywords", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "publication_versions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("publication_id", sa.BigInteger(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("classification", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "publication_companies",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("publication_id", sa.BigInteger(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("cnpj", sa.String(length=20), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "publication_files",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("publication_id", sa.BigInteger(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("file_type", sa.String(length=80), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("filename", sa.String(length=500), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("storage_path", sa.String(length=1000), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "classification_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("publication_id", sa.BigInteger(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("keywords", postgresql.ARRAY(sa.String(length=120)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_sources_enabled", "sources", ["enabled"])
    op.create_index("ix_collection_runs_source_status", "collection_runs", ["source_id", "status"])
    op.create_index("ix_collection_runs_started_at", "collection_runs", ["started_at"])
    op.create_index("ux_publications_source_external_id", "publications", ["source_id", "external_id"], unique=True, postgresql_where=sa.text("external_id IS NOT NULL"))
    op.create_index("ix_publications_source_id", "publications", ["source_id"])
    op.create_index("ix_publications_content_hash", "publications", ["content_hash"])
    op.create_index("ix_publications_state_municipality", "publications", ["state", "municipality"])
    op.create_index("ix_publications_published_at", "publications", ["published_at"])
    op.create_index("ix_publications_publication_type", "publications", ["publication_type"])
    op.create_index("ix_publications_tags_gin", "publications", ["tags"], postgresql_using="gin")
    op.create_index("ix_publications_keywords_gin", "publications", ["keywords"], postgresql_using="gin")
    op.create_index("ix_publications_raw_payload_gin", "publications", ["raw_payload"], postgresql_using="gin")
    op.execute("CREATE INDEX ix_publications_object_trgm ON publications USING gin (object gin_trgm_ops)")
    op.execute("CREATE INDEX ix_publications_clean_text_trgm ON publications USING gin (clean_text gin_trgm_ops)")
    op.create_index("ux_publication_versions_publication_version", "publication_versions", ["publication_id", "version_number"], unique=True)
    op.create_index("ix_publication_versions_collected_at", "publication_versions", ["collected_at"])
    op.create_index("ix_publication_companies_cnpj", "publication_companies", ["cnpj"])
    op.create_index("ix_publication_files_publication_id", "publication_files", ["publication_id"])
    op.create_index("ix_classification_results_publication_id", "classification_results", ["publication_id"])


def downgrade() -> None:
    op.drop_index("ix_classification_results_publication_id", table_name="classification_results")
    op.drop_index("ix_publication_files_publication_id", table_name="publication_files")
    op.drop_index("ix_publication_companies_cnpj", table_name="publication_companies")
    op.drop_index("ix_publication_versions_collected_at", table_name="publication_versions")
    op.drop_index("ux_publication_versions_publication_version", table_name="publication_versions")
    op.execute("DROP INDEX IF EXISTS ix_publications_clean_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_publications_object_trgm")
    op.drop_index("ix_publications_raw_payload_gin", table_name="publications")
    op.drop_index("ix_publications_keywords_gin", table_name="publications")
    op.drop_index("ix_publications_tags_gin", table_name="publications")
    op.drop_index("ix_publications_publication_type", table_name="publications")
    op.drop_index("ix_publications_published_at", table_name="publications")
    op.drop_index("ix_publications_state_municipality", table_name="publications")
    op.drop_index("ix_publications_content_hash", table_name="publications")
    op.drop_index("ix_publications_source_id", table_name="publications")
    op.drop_index("ux_publications_source_external_id", table_name="publications")
    op.drop_index("ix_collection_runs_started_at", table_name="collection_runs")
    op.drop_index("ix_collection_runs_source_status", table_name="collection_runs")
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_table("classification_results")
    op.drop_table("publication_files")
    op.drop_table("publication_companies")
    op.drop_table("publication_versions")
    op.drop_table("publications")
    op.drop_table("collection_runs")
    op.drop_table("sources")

