from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

NORMALIZED_FIELDS = (
    "source",
    "source_system",
    "ano",
    "orgao",
    "modalidade",
    "numero_licitacao",
    "numero_processo",
    "numero_contrato",
    "objeto",
    "fornecedor",
    "fornecedor_documento",
    "valor_contrato",
    "data_assinatura",
    "data_publicacao",
    "evento",
    "retranca",
    "raw",
)

FIELD_ALIASES = {
    "orgao": ("orgao", "Orgao", "nome_orgao", "unidade", "secretaria"),
    "modalidade": ("modalidade", "Modalidade", "tipo_modalidade", "modalidade_licitacao"),
    "numero_licitacao": (
        "numero_licitacao",
        "numero licitacao",
        "Numero_Licitacao",
        "n_licitacao",
        "licitacao",
    ),
    "numero_processo": (
        "numero_processo",
        "processo",
        "Processo",
        "NumeroProcesso",
        "Numero_Processo",
    ),
    "numero_contrato": (
        "numero_contrato",
        "numero contrato",
        "NumeroContrato",
        "NumeroContrato",
        "Contrato",
        "contrato",
    ),
    "objeto": ("objeto", "Objeto", "descricao_objeto", "descricao", "Descricao"),
    "fornecedor": ("fornecedor", "Fornecedor", "contratada", "Contratada", "empresa", "Empresa"),
    "fornecedor_documento": (
        "fornecedor_documento",
        "cnpj",
        "CNPJ",
        "cpf_cnpj",
        "documento_fornecedor",
        "CNPJFornecedor",
    ),
    "valor_contrato": (
        "valor_contrato",
        "ValorContrato",
        "valor contrato",
        "valor",
        "Valor",
        "valor_total",
    ),
    "data_assinatura": (
        "data_assinatura",
        "DataAssinaturaExtrato",
        "data assinatura",
        "data_assinatura_extrato",
        "assinatura",
    ),
    "data_publicacao": (
        "data_publicacao",
        "DataPublicacaoExtrato",
        "data publicacao",
        "data_publicacao_extrato",
        "publicacao",
    ),
    "evento": ("evento", "Evento", "tipo_evento", "tipo", "situacao", "Situacao"),
    "retranca": ("retranca", "Retranca"),
}

def normalize_record(raw: Mapping[str, Any], ano: int, source: str, source_system: str) -> dict[str, Any]:
    indexed = {normalize_key(key): value for key, value in raw.items()}
    normalized: dict[str, Any] = {
        "source": source,
        "source_system": source_system,
        "ano": ano,
        "raw": dict(raw),
    }

    for field in NORMALIZED_FIELDS:
        if field in {"source", "source_system", "ano", "raw"}:
            continue
        normalized[field] = first_value(indexed, FIELD_ALIASES.get(field, (field,)))

    return normalized


def normalize_records(records: list[Mapping[str, Any]], ano: int, source: str, source_system: str) -> list[dict[str, Any]]:
    return [normalize_record(record, ano=ano, source=source, source_system=source_system) for record in records]


def normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


EXPECTED_SOURCE_FIELD_KEYS = {
    normalize_key(value)
    for aliases in FIELD_ALIASES.values()
    for value in aliases
}


def first_value(indexed: Mapping[str, Any], aliases: tuple[str, ...]) -> Any | None:
    for alias in aliases:
        value = indexed.get(normalize_key(alias))
        if value not in (None, ""):
            return value
    return None


def record_has_expected_fields(record: Mapping[str, Any]) -> bool:
    keys = {normalize_key(key) for key in record.keys()}
    return bool(keys & EXPECTED_SOURCE_FIELD_KEYS)
