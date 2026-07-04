from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from hermes.connectors.doc_sp.auth import ApilibAuthError, ApilibAuthenticator, ApilibCredentials
from hermes.connectors.pmsp.licitacoes.provider import PmspLicitacoesProvider
from hermes.database.models import PmspLicitacao
from hermes.database.session import SessionLocal


@dataclass(slots=True)
class YearIngestionSummary:
    ano: int
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    source_used: str | None = None
    total: int | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ano": self.ano,
            "fetched": self.fetched,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "source_used": self.source_used,
            "total": self.total,
            "dry_run": self.dry_run,
        }


def build_source_hash(record: dict[str, Any]) -> str:
    raw = record.get("raw")
    identity_fields = {
        "raw_id": raw.get("_id") if isinstance(raw, dict) else None,
        "raw_id_alt": raw.get("id") if isinstance(raw, dict) else None,
        "orgao": record.get("orgao"),
        "numero_processo": record.get("numero_processo"),
        "numero_contrato": record.get("numero_contrato"),
        "numero_licitacao": record.get("numero_licitacao"),
        "retranca": record.get("retranca"),
        "modalidade": record.get("modalidade"),
    }
    identity = {
        "source": record.get("source"),
        "source_system": record.get("source_system"),
        "ano": record.get("ano"),
        **identity_fields,
    }

    if not any(value not in (None, "") for value in identity_fields.values()):
        identity["raw"] = raw

    serialized = json.dumps(identity, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def upsert_record(session: Session, record: dict[str, Any]) -> str:
    source_hash = build_source_hash(record)
    existing = session.execute(
        select(PmspLicitacao).where(PmspLicitacao.source_hash == source_hash)
    ).scalar_one_or_none()
    values = record_to_model_values(record, source_hash)

    if existing is None:
        session.add(PmspLicitacao(**values))
        session.flush()
        return "inserted"

    if not model_has_changes(existing, values):
        return "skipped"

    for key, value in values.items():
        if key in {"source_hash", "created_at"}:
            continue
        setattr(existing, key, value)
    existing.updated_at = datetime.now(UTC)
    session.flush()
    return "updated"


def ingest_year(
    ano: int,
    limite: int = 100,
    offset: int = 0,
    *,
    session: Session | None = None,
    provider: PmspLicitacoesProvider | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    owns_session = session is None
    active_session = session or SessionLocal()
    summary = YearIngestionSummary(ano=ano, dry_run=dry_run)

    try:
        active_provider = provider or build_provider()
        result = active_provider.list_by_year(ano, limite=limite, offset=offset)
        summary.source_used = result.source_used
        summary.total = result.total
        summary.fetched = len(result.records)
        summary.errors.extend(error.message for error in result.errors)

        if dry_run:
            summary.skipped = summary.fetched
            return summary.to_dict()

        for record in result.records:
            try:
                action = upsert_record(active_session, record)
            except Exception as exc:
                summary.errors.append(f"{exc.__class__.__name__}: {exc}")
                continue

            if action == "inserted":
                summary.inserted += 1
            elif action == "updated":
                summary.updated += 1
            else:
                summary.skipped += 1

        active_session.commit()
        return summary.to_dict()
    except Exception as exc:
        active_session.rollback()
        summary.errors.append(f"{exc.__class__.__name__}: {exc}")
        return summary.to_dict()
    finally:
        if owns_session:
            active_session.close()


def ingest_year_range(
    start_year: int,
    end_year: int,
    limite: int = 100,
    *,
    offset: int = 0,
    session: Session | None = None,
    provider: PmspLicitacoesProvider | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    years = range(start_year, end_year + 1)
    summaries = [
        ingest_year(
            ano,
            limite=limite,
            offset=offset,
            session=session,
            provider=provider,
            dry_run=dry_run,
        )
        for ano in years
    ]
    return {
        "start_year": start_year,
        "end_year": end_year,
        "fetched": sum(item["fetched"] for item in summaries),
        "inserted": sum(item["inserted"] for item in summaries),
        "updated": sum(item["updated"] for item in summaries),
        "skipped": sum(item["skipped"] for item in summaries),
        "errors": [error for item in summaries for error in item["errors"]],
        "years": summaries,
        "dry_run": dry_run,
    }


def build_provider() -> PmspLicitacoesProvider:
    try:
        credentials = ApilibCredentials.from_env()
        token = ApilibAuthenticator(credentials).request_token().token
        return PmspLicitacoesProvider(token=token)
    except ApilibAuthError:
        return PmspLicitacoesProvider(token=None)


def record_to_model_values(record: dict[str, Any], source_hash: str) -> dict[str, Any]:
    return {
        "source": optional_str(record.get("source")) or "ckan",
        "source_system": optional_str(record.get("source_system")) or "PMSP Dados Abertos CKAN",
        "ano": int(record.get("ano") or 0),
        "orgao": optional_str(record.get("orgao")),
        "modalidade": optional_str(record.get("modalidade")),
        "numero_licitacao": optional_str(record.get("numero_licitacao")),
        "numero_processo": optional_str(record.get("numero_processo")),
        "numero_contrato": optional_str(record.get("numero_contrato")),
        "objeto": optional_str(record.get("objeto")),
        "fornecedor": optional_str(record.get("fornecedor")),
        "fornecedor_documento": optional_str(record.get("fornecedor_documento")),
        "valor_contrato": parse_decimal(record.get("valor_contrato")),
        "data_assinatura": parse_date(record.get("data_assinatura")),
        "data_publicacao": parse_date(record.get("data_publicacao")),
        "evento": optional_str(record.get("evento")),
        "retranca": optional_str(record.get("retranca")),
        "source_hash": source_hash,
        "raw_json": record.get("raw") if isinstance(record.get("raw"), dict) else {"value": record.get("raw")},
    }


def model_has_changes(model: PmspLicitacao, values: dict[str, Any]) -> bool:
    for key, value in values.items():
        if key == "source_hash":
            continue
        if getattr(model, key) != value:
            return True
    return False


def parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    candidates = [
        text,
        text[:10],
        text.replace("T", " ")[:19],
    ]
    for candidate in candidates:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
