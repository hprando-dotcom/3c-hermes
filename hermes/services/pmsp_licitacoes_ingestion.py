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
from hermes.connectors.pmsp.licitacoes.normalizer import (
    PARSER_METADATA_KEYS,
    detect_record_format,
    expand_record,
    looks_like_csv,
    normalize_key,
    normalize_record,
    parse_record,
)
from hermes.connectors.pmsp.licitacoes.provider import PmspLicitacoesProvider
from hermes.database.models import PmspLicitacao
from hermes.database.session import SessionLocal


class PmspLicitacoesValidationError(ValueError):
    """Raised when a normalized record is unsafe to persist."""


@dataclass(slots=True)
class YearIngestionSummary:
    ano: int
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
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
            "diagnostics": self.diagnostics,
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
    validate_record_before_upsert(record)
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
        summary.errors.extend(error.message for error in result.errors)
        resource_context = resource_context_from_provider_result(result)
        prepared_records = prepare_provider_records(
            result.records,
            ano=ano,
            source=result.source_used,
            source_system=result.source_system,
            resource_context=resource_context,
        )
        summary.fetched = len(prepared_records)

        if dry_run:
            summary.skipped = summary.fetched
            for prepared in prepared_records:
                diagnostic = prepared["diagnostic"]
                diagnostic["decision"] = "dry_run"
                summary.diagnostics.append(diagnostic)
            return summary.to_dict()

        for prepared in prepared_records:
            record = prepared["record"]
            diagnostic = prepared["diagnostic"]
            try:
                validate_record_before_upsert(record, diagnostic=diagnostic)
                diagnostic["decision"] = "persistir"
                action = upsert_record(active_session, record)
                active_session.commit()
            except PmspLicitacoesValidationError as exc:
                active_session.rollback()
                diagnostic["decision"] = "bloquear"
                diagnostic["error"] = str(exc)
                summary.diagnostics.append(diagnostic)
                summary.skipped += 1
                summary.errors.append(str(exc))
                continue
            except Exception as exc:
                active_session.rollback()
                diagnostic["decision"] = "erro"
                diagnostic["error"] = f"{exc.__class__.__name__}: {exc}"
                summary.diagnostics.append(diagnostic)
                summary.errors.append(f"{exc.__class__.__name__}: {exc}")
                continue

            diagnostic["action"] = action
            summary.diagnostics.append(diagnostic)
            if action == "inserted":
                summary.inserted += 1
            elif action == "updated":
                summary.updated += 1
            else:
                summary.skipped += 1

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
        "diagnostics": [diagnostic for item in summaries for diagnostic in item.get("diagnostics", [])],
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


def normalize_provider_records(
    records: list[dict[str, Any]],
    *,
    ano: int,
    source: str | None,
    source_system: str | None,
) -> list[dict[str, Any]]:
    return [
        prepared["record"]
        for prepared in prepare_provider_records(records, ano=ano, source=source, source_system=source_system)
    ]


def normalize_provider_record(
    record: dict[str, Any],
    *,
    ano: int,
    source: str | None,
    source_system: str | None,
) -> list[dict[str, Any]]:
    return [
        prepared["record"]
        for prepared in prepare_provider_record(record, ano=ano, source=source, source_system=source_system)
    ]


def prepare_provider_records(
    records: list[dict[str, Any]],
    *,
    ano: int,
    source: str | None,
    source_system: str | None,
    resource_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for record in records:
        prepared.extend(
            prepare_provider_record(
                record,
                ano=ano,
                source=source,
                source_system=source_system,
                resource_context=resource_context,
            )
        )
    return prepared


def prepare_provider_record(
    record: dict[str, Any],
    *,
    ano: int,
    source: str | None,
    source_system: str | None,
    resource_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw = record.get("raw") if isinstance(record, dict) else None
    raw_record = raw if isinstance(raw, (dict, str)) else record
    record_source = optional_str(record.get("source")) or source or "ckan"
    record_source_system = optional_str(record.get("source_system")) or source_system or "PMSP Dados Abertos CKAN"

    parsed_records = expand_record(raw_record)
    if not parsed_records:
        parsed_records = [parse_record(raw_record)]

    prepared: list[dict[str, Any]] = []
    for parsed_record in parsed_records:
        normalized = normalize_record(parsed_record, ano=ano, source=record_source, source_system=record_source_system)
        diagnostic = build_record_diagnostic(
            raw_record=raw_record,
            parsed_record=parsed_record,
            normalized=normalized,
            resource_context=resource_context,
        )
        prepared.append({"record": normalized, "diagnostic": diagnostic})
    return prepared


def has_unexpanded_csv_orgao(record: dict[str, Any]) -> bool:
    orgao = record.get("orgao")
    if not isinstance(orgao, str):
        return False
    has_separator = "," in orgao or ";" in orgao
    if not has_separator:
        return False
    upper_orgao = orgao.upper()
    missing_core_fields = not record.get("modalidade") or not record.get("objeto") or not record.get("numero_processo")
    suspicious_fragments = (
        "CONVITE",
        "EXTRATO",
        "PJ",
        "DIAS",
        "PREG",
        "CONCORR",
        "/SP-",
    )
    return (
        looks_like_csv(orgao)
        or orgao.count(",") + orgao.count(";") >= 4
        or ("," in orgao and any(fragment in upper_orgao for fragment in suspicious_fragments))
        or (len(orgao) > 200 and missing_core_fields)
        or bool(re.search(r"\b20\d{2}-\d\.\d{3}\.\d{3}-\d\b", orgao))
    )


def validate_record_before_upsert(record: dict[str, Any], diagnostic: dict[str, Any] | None = None) -> None:
    if not has_unexpanded_csv_orgao(record):
        return
    context = diagnostic or build_record_diagnostic(
        raw_record=record.get("raw") if isinstance(record.get("raw"), (dict, str)) else record,
        parsed_record=record,
        normalized=record,
        resource_context=None,
    )
    raise PmspLicitacoesValidationError(
        "single_field_csv_not_expanded_before_upsert: "
        f"{record_identity(record)} "
        f"resource_id={context.get('resource_id')} "
        f"raw_json={summarize_value(context.get('raw_useful'))}"
    )


def build_record_diagnostic(
    *,
    raw_record: dict[str, Any] | str,
    parsed_record: dict[str, Any] | str,
    normalized: dict[str, Any],
    resource_context: dict[str, Any] | None,
) -> dict[str, Any]:
    resource_context = resource_context or {}
    return {
        "resource_id": resource_context.get("resource_id"),
        "resource_name": resource_context.get("resource_name"),
        "tipo_detectado": detect_record_format(raw_record),
        "raw_keys": list(raw_record.keys()) if isinstance(raw_record, dict) else [],
        "raw_useful": useful_raw_values(raw_record),
        "parsed_keys": list(parsed_record.keys()) if isinstance(parsed_record, dict) else [],
        "normalized": {
            "orgao": normalized.get("orgao"),
            "modalidade": normalized.get("modalidade"),
            "numero_processo": normalized.get("numero_processo"),
        },
    }


def useful_raw_values(raw_record: dict[str, Any] | str) -> dict[str, Any] | str:
    if not isinstance(raw_record, dict):
        return summarize_value(raw_record)
    return {
        str(key): summarize_value(value)
        for key, value in raw_record.items()
        if normalize_key(key) not in PARSER_METADATA_KEYS
    }


def summarize_value(value: Any, limit: int = 300) -> Any:
    if isinstance(value, dict):
        return {str(key): summarize_value(item, limit=limit) for key, item in value.items()}
    if isinstance(value, list):
        return [summarize_value(item, limit=limit) for item in value[:5]]
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}...[truncated]"


def resource_context_from_provider_result(result: Any) -> dict[str, Any]:
    selected_resource: dict[str, Any] = {}
    ckan = result.ckan if isinstance(getattr(result, "ckan", None), dict) else {}
    apilib = result.apilib if isinstance(getattr(result, "apilib", None), dict) else {}
    if isinstance(ckan.get("selected_resource"), dict):
        selected_resource = ckan["selected_resource"]
    return {
        "resource_id": selected_resource.get("resource_id") or ckan.get("resource_id") or apilib.get("resource_id"),
        "resource_name": selected_resource.get("name") or selected_resource.get("title") or ckan.get("resource_name"),
    }


def record_identity(record: dict[str, Any]) -> str:
    raw = record.get("raw")
    raw_id = raw.get("_id") or raw.get("id") if isinstance(raw, dict) else None
    parts = [
        f"source={record.get('source')}",
        f"ano={record.get('ano')}",
    ]
    if raw_id is not None:
        parts.append(f"raw_id={raw_id}")
    return " ".join(parts)


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
