from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Identity, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from hermes.database.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_name: Mapped[str | None] = mapped_column(String(120))
    base_url: Mapped[str | None] = mapped_column(String(500))
    scope: Mapped[str | None] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    publications: Mapped[list[Publication]] = relationship(back_populates="source")
    public_sources: Mapped[list[PublicSource]] = relationship(back_populates="source")


class PublicSource(Base):
    __tablename__ = "public_sources"
    __table_args__ = (
        UniqueConstraint("normalized_url", name="uq_public_sources_normalized_url"),
        Index("ix_public_sources_source_id", "source_id"),
        Index("ix_public_sources_status", "status"),
        Index("ix_public_sources_last_inspected_at", "last_inspected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, server_default=text("'official_site'"))
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'active'"))
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(200))
    detected_links: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    detected_endpoints: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    last_inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    source: Mapped[Source | None] = relationship(back_populates="public_sources")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_found: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    records_inserted: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    records_updated: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = (
        Index("ux_publications_source_external_id", "source_id", "external_id", unique=True, postgresql_where=text("external_id IS NOT NULL")),
        Index("ix_publications_source_id", "source_id"),
        Index("ix_publications_content_hash", "content_hash"),
        Index("ix_publications_state_municipality", "state", "municipality"),
        Index("ix_publications_published_at", "published_at"),
        Index("ix_publications_publication_type", "publication_type"),
        Index("ix_publications_tags_gin", "tags", postgresql_using="gin"),
        Index("ix_publications_keywords_gin", "keywords", postgresql_using="gin"),
        Index("ix_publications_raw_payload_gin", "raw_payload", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(500))
    entity: Mapped[str | None] = mapped_column(String(500))
    state: Mapped[str | None] = mapped_column(String(2))
    municipality: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(255))
    api_name: Mapped[str | None] = mapped_column(String(120))
    publication_type: Mapped[str | None] = mapped_column(String(120))
    object_description: Mapped[str | None] = mapped_column("object", Text)
    modality: Mapped[str | None] = mapped_column(String(120))
    situation: Mapped[str | None] = mapped_column(String(120))
    number: Mapped[str | None] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(Integer)
    winner_company_name: Mapped[str | None] = mapped_column(String(500))
    winner_cnpj: Mapped[str | None] = mapped_column(String(20))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    awarded_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    contracted_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    addendum_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    deadline: Mapped[str | None] = mapped_column(String(255))
    validity_start: Mapped[date | None] = mapped_column(Date)
    validity_end: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_date: Mapped[date | None] = mapped_column(Date)
    links: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    raw_text: Mapped[str | None] = mapped_column(Text)
    clean_text: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, server_default=text("ARRAY[]::varchar[]"))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, server_default=text("ARRAY[]::varchar[]"))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    source: Mapped[Source] = relationship(back_populates="publications")
    versions: Mapped[list[PublicationVersion]] = relationship(back_populates="publication", cascade="all, delete-orphan")
    companies: Mapped[list[PublicationCompany]] = relationship(back_populates="publication", cascade="all, delete-orphan")
    files: Mapped[list[PublicationFile]] = relationship(back_populates="publication", cascade="all, delete-orphan")
    classification_results: Mapped[list[ClassificationResultModel]] = relationship(back_populates="publication", cascade="all, delete-orphan")


class PublicationVersion(Base):
    __tablename__ = "publication_versions"
    __table_args__ = (
        Index("ux_publication_versions_publication_version", "publication_id", "version_number", unique=True),
        Index("ix_publication_versions_collected_at", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    raw_text: Mapped[str | None] = mapped_column(Text)
    clean_text: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    publication: Mapped[Publication] = relationship(back_populates="versions")


class PublicationCompany(Base):
    __tablename__ = "publication_companies"
    __table_args__ = (Index("ix_publication_companies_cnpj", "cnpj"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(20))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    publication: Mapped[Publication] = relationship(back_populates="companies")


class PublicationFile(Base):
    __tablename__ = "publication_files"
    __table_args__ = (Index("ix_publication_files_publication_id", "publication_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(80))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    filename: Mapped[str | None] = mapped_column(String(500))
    checksum: Mapped[str | None] = mapped_column(String(128))
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    publication: Mapped[Publication] = relationship(back_populates="files")


class ClassificationResultModel(Base):
    __tablename__ = "classification_results"
    __table_args__ = (Index("ix_classification_results_publication_id", "publication_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, server_default=text("ARRAY[]::varchar[]"))
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, server_default=text("ARRAY[]::varchar[]"))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    publication: Mapped[Publication] = relationship(back_populates="classification_results")


class PmspLicitacao(Base):
    __tablename__ = "pmsp_licitacoes"
    __table_args__ = (
        UniqueConstraint("source_hash", name="uq_pmsp_licitacoes_source_hash"),
        Index("ix_pmsp_licitacoes_ano", "ano"),
        Index("ix_pmsp_licitacoes_orgao", "orgao"),
        Index("ix_pmsp_licitacoes_numero_processo", "numero_processo"),
        Index("ix_pmsp_licitacoes_numero_contrato", "numero_contrato"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_system: Mapped[str] = mapped_column(String(255), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    orgao: Mapped[str | None] = mapped_column(String(500))
    modalidade: Mapped[str | None] = mapped_column(String(120))
    numero_licitacao: Mapped[str | None] = mapped_column(String(120))
    numero_processo: Mapped[str | None] = mapped_column(String(120))
    numero_contrato: Mapped[str | None] = mapped_column(String(120))
    objeto: Mapped[str | None] = mapped_column(Text)
    fornecedor: Mapped[str | None] = mapped_column(String(500))
    fornecedor_documento: Mapped[str | None] = mapped_column(String(40))
    valor_contrato: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    data_assinatura: Mapped[date | None] = mapped_column(Date)
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    evento: Mapped[str | None] = mapped_column(String(120))
    retranca: Mapped[str | None] = mapped_column(String(255))
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TceSpMunicipio(Base):
    __tablename__ = "tcesp_municipios"
    __table_args__ = (
        UniqueConstraint("municipio_slug", name="uq_tcesp_municipios_slug"),
        Index("ix_tcesp_municipios_extenso", "municipio_extenso"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    municipio_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    municipio_extenso: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TceSpDespesa(Base):
    __tablename__ = "tcesp_despesas"
    __table_args__ = (
        Index("ix_tcesp_despesas_municipio_periodo", "municipio_slug", "exercicio", "mes_numero"),
        Index("ix_tcesp_despesas_fornecedor", "nm_fornecedor"),
        Index("ix_tcesp_despesas_orgao", "orgao"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    municipio_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    municipio_extenso: Mapped[str | None] = mapped_column(String(255))
    exercicio: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_nome: Mapped[str | None] = mapped_column(String(40))
    orgao: Mapped[str | None] = mapped_column(String(500))
    evento: Mapped[str | None] = mapped_column(String(120))
    nr_empenho: Mapped[str | None] = mapped_column(String(120))
    id_fornecedor: Mapped[str | None] = mapped_column(String(255))
    nm_fornecedor: Mapped[str | None] = mapped_column(String(500))
    dt_emissao_despesa: Mapped[date | None] = mapped_column(Date)
    vl_despesa: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(String(80), nullable=False, server_default=text("'tcesp'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TceSpReceita(Base):
    __tablename__ = "tcesp_receitas"
    __table_args__ = (
        Index("ix_tcesp_receitas_municipio_periodo", "municipio_slug", "exercicio", "mes_numero"),
        Index("ix_tcesp_receitas_orgao", "orgao"),
        Index("ix_tcesp_receitas_fonte", "ds_fonte_recurso"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    municipio_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    municipio_extenso: Mapped[str | None] = mapped_column(String(255))
    exercicio: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    mes_nome: Mapped[str | None] = mapped_column(String(40))
    orgao: Mapped[str | None] = mapped_column(String(500))
    ds_fonte_recurso: Mapped[str | None] = mapped_column(String(500))
    ds_cd_aplicacao_fixo: Mapped[str | None] = mapped_column(String(500))
    ds_alinea: Mapped[str | None] = mapped_column(String(500))
    ds_subalinea: Mapped[str | None] = mapped_column(Text)
    vl_arrecadacao: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(String(80), nullable=False, server_default=text("'tcesp'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
