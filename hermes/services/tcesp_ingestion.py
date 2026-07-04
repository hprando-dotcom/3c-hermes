from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from hermes.connectors.tcesp.client import TceSpClient
from hermes.connectors.tcesp.normalizer import normalize_despesa, normalize_municipio, normalize_receita, slugify
from hermes.database.models import TceSpDespesa, TceSpMunicipio, TceSpReceita
from hermes.database.session import SessionLocal


@dataclass(slots=True)
class IngestionResult:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors or [],
        }


def ingest_municipios(
    *,
    session: Session | None = None,
    client: TceSpClient | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    owns_session = session is None
    active_session = session or SessionLocal()
    result = IngestionResult(errors=[])
    try:
        active_client = client or TceSpClient()
        records = [normalize_municipio(item) for item in active_client.fetch_municipios()]
        result.fetched = len(records)
        if dry_run:
            result.skipped = result.fetched
            return result.to_dict()
        for record in records:
            action = upsert_municipio(active_session, record)
            increment(result, action)
        active_session.commit()
        return result.to_dict()
    except Exception as exc:
        active_session.rollback()
        result.errors.append(f"{exc.__class__.__name__}: {exc}")
        return result.to_dict()
    finally:
        if owns_session:
            active_session.close()


def ingest_despesas(
    municipio: str,
    ano: int,
    mes: int,
    *,
    session: Session | None = None,
    client: TceSpClient | None = None,
    dry_run: bool = False,
    limite: int | None = None,
) -> dict[str, Any]:
    owns_session = session is None
    active_session = session or SessionLocal()
    result = IngestionResult(errors=[])
    try:
        active_client = client or TceSpClient()
        municipio_slug = slugify(municipio)
        municipio_extenso = find_municipio_name(active_session, municipio_slug)
        raw_records = active_client.fetch_despesas(municipio_slug, ano, mes)
        if limite is not None:
            raw_records = raw_records[:limite]
        records = [
            normalize_despesa(item, municipio_slug=municipio_slug, exercicio=ano, mes=mes, municipio_extenso=municipio_extenso)
            for item in raw_records
        ]
        result.fetched = len(records)
        if dry_run:
            result.skipped = result.fetched
            return result.to_dict()
        for record in records:
            try:
                action = upsert_despesa(active_session, record)
                active_session.commit()
                increment(result, action)
            except Exception as exc:
                active_session.rollback()
                result.errors.append(f"{exc.__class__.__name__}: {exc}")
        return result.to_dict()
    except Exception as exc:
        active_session.rollback()
        result.errors.append(f"{exc.__class__.__name__}: {exc}")
        return result.to_dict()
    finally:
        if owns_session:
            active_session.close()


def ingest_receitas(
    municipio: str,
    ano: int,
    mes: int,
    *,
    session: Session | None = None,
    client: TceSpClient | None = None,
    dry_run: bool = False,
    limite: int | None = None,
) -> dict[str, Any]:
    owns_session = session is None
    active_session = session or SessionLocal()
    result = IngestionResult(errors=[])
    try:
        active_client = client or TceSpClient()
        municipio_slug = slugify(municipio)
        municipio_extenso = find_municipio_name(active_session, municipio_slug)
        raw_records = active_client.fetch_receitas(municipio_slug, ano, mes)
        if limite is not None:
            raw_records = raw_records[:limite]
        records = [
            normalize_receita(item, municipio_slug=municipio_slug, exercicio=ano, mes=mes, municipio_extenso=municipio_extenso)
            for item in raw_records
        ]
        result.fetched = len(records)
        if dry_run:
            result.skipped = result.fetched
            return result.to_dict()
        for record in records:
            try:
                action = upsert_receita(active_session, record)
                active_session.commit()
                increment(result, action)
            except Exception as exc:
                active_session.rollback()
                result.errors.append(f"{exc.__class__.__name__}: {exc}")
        return result.to_dict()
    except Exception as exc:
        active_session.rollback()
        result.errors.append(f"{exc.__class__.__name__}: {exc}")
        return result.to_dict()
    finally:
        if owns_session:
            active_session.close()


def upsert_municipio(session: Session, record: dict[str, Any]) -> str:
    existing = session.execute(
        select(TceSpMunicipio).where(TceSpMunicipio.municipio_slug == record["municipio_slug"])
    ).scalar_one_or_none()
    if existing is None:
        session.add(TceSpMunicipio(**record))
        return "inserted"
    changed = False
    for key, value in record.items():
        if getattr(existing, key) != value:
            setattr(existing, key, value)
            changed = True
    return "updated" if changed else "skipped"


def upsert_despesa(session: Session, record: dict[str, Any]) -> str:
    existing = session.execute(
        select(TceSpDespesa).where(
            TceSpDespesa.municipio_slug == record["municipio_slug"],
            TceSpDespesa.exercicio == record["exercicio"],
            TceSpDespesa.mes_numero == record["mes_numero"],
            TceSpDespesa.nr_empenho == record.get("nr_empenho"),
            TceSpDespesa.id_fornecedor == record.get("id_fornecedor"),
            TceSpDespesa.vl_despesa == record.get("vl_despesa"),
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(TceSpDespesa(**record))
        return "inserted"
    return update_model(existing, record)


def upsert_receita(session: Session, record: dict[str, Any]) -> str:
    existing = session.execute(
        select(TceSpReceita).where(
            TceSpReceita.municipio_slug == record["municipio_slug"],
            TceSpReceita.exercicio == record["exercicio"],
            TceSpReceita.mes_numero == record["mes_numero"],
            TceSpReceita.orgao == record.get("orgao"),
            TceSpReceita.ds_fonte_recurso == record.get("ds_fonte_recurso"),
            TceSpReceita.ds_alinea == record.get("ds_alinea"),
            TceSpReceita.ds_subalinea == record.get("ds_subalinea"),
            TceSpReceita.vl_arrecadacao == record.get("vl_arrecadacao"),
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(TceSpReceita(**record))
        return "inserted"
    return update_model(existing, record)


def update_model(model: Any, values: dict[str, Any]) -> str:
    changed = False
    for key, value in values.items():
        if getattr(model, key) != value:
            setattr(model, key, value)
            changed = True
    return "updated" if changed else "skipped"


def find_municipio_name(session: Session, municipio_slug: str) -> str | None:
    return session.scalar(
        select(TceSpMunicipio.municipio_extenso).where(TceSpMunicipio.municipio_slug == municipio_slug)
    )


def increment(result: IngestionResult, action: str) -> None:
    if action == "inserted":
        result.inserted += 1
    elif action == "updated":
        result.updated += 1
    else:
        result.skipped += 1
