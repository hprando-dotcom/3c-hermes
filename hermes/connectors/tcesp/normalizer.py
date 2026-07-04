from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def normalize_municipio(raw: Mapping[str, Any]) -> dict[str, Any]:
    slug = optional_str(raw.get("municipio") or raw.get("municipio_slug") or raw.get("slug"))
    name = optional_str(raw.get("municipio_extenso") or raw.get("nome") or raw.get("name") or slug)
    return {
        "municipio_slug": slugify(slug or name or ""),
        "municipio_extenso": name or slug or "",
        "raw_json": dict(raw),
    }


def normalize_despesa(
    raw: Mapping[str, Any],
    *,
    municipio_slug: str,
    exercicio: int,
    mes: int,
    municipio_extenso: str | None = None,
) -> dict[str, Any]:
    return {
        "municipio_slug": slugify(municipio_slug),
        "municipio_extenso": municipio_extenso,
        "exercicio": exercicio,
        "mes_numero": mes,
        "mes_nome": optional_str(raw.get("mes")) or MONTH_NAMES.get(mes),
        "orgao": optional_str(raw.get("orgao")),
        "evento": optional_str(raw.get("evento")),
        "nr_empenho": optional_str(raw.get("nr_empenho")),
        "id_fornecedor": optional_str(raw.get("id_fornecedor")),
        "nm_fornecedor": optional_str(raw.get("nm_fornecedor")),
        "dt_emissao_despesa": parse_date(raw.get("dt_emissao_despesa")),
        "vl_despesa": parse_decimal(raw.get("vl_despesa")),
        "raw_json": dict(raw),
        "source": "tcesp",
    }


def normalize_receita(
    raw: Mapping[str, Any],
    *,
    municipio_slug: str,
    exercicio: int,
    mes: int,
    municipio_extenso: str | None = None,
) -> dict[str, Any]:
    return {
        "municipio_slug": slugify(municipio_slug),
        "municipio_extenso": municipio_extenso,
        "exercicio": exercicio,
        "mes_numero": mes,
        "mes_nome": optional_str(raw.get("mes")) or MONTH_NAMES.get(mes),
        "orgao": optional_str(raw.get("orgao")),
        "ds_fonte_recurso": optional_str(raw.get("ds_fonte_recurso")),
        "ds_cd_aplicacao_fixo": optional_str(raw.get("ds_cd_aplicacao_fixo")),
        "ds_alinea": optional_str(raw.get("ds_alinea")),
        "ds_subalinea": optional_str(raw.get("ds_subalinea")),
        "vl_arrecadacao": parse_decimal(raw.get("vl_arrecadacao")),
        "raw_json": dict(raw),
        "source": "tcesp",
    }


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
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None
