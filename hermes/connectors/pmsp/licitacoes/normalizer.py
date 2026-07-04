from __future__ import annotations

import csv
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

FALLBACK_CSV_COLUMNS = (
    "Orgao",
    "Retranca",
    "Modalidade",
    "Numero_Licitacao",
    "Numero_Processo",
    "Objeto",
    "Fornecedor",
    "Fornecedor_Documento",
    "ValorContrato",
    "NumeroContrato",
    "DataAssinaturaExtrato",
    "DataPublicacaoExtrato",
    "Evento",
)

E_NEGOCIOS_CSV_COLUMNS = (
    "Orgao",
    "Retranca",
    "Modalidade",
    "Numero_Licitacao",
    "Numero_Processo",
    "Evento",
    "Objeto",
    "DataPublicacaoExtrato",
    "Fornecedor",
    "Fornecedor_Tipo",
    "Fornecedor_Documento",
    "DataAssinaturaExtrato",
    "Prazo",
    "Prazo_Unidade",
    "ValorContrato",
    "NumeroContrato",
)

CSV_CONTAINER_FIELD_KEYS = {
    "arquivo",
    "content",
    "linha",
    "nomedoorgao",
    "orgao",
    "record",
    "records",
    "registro",
    "value",
}

PARSER_METADATA_KEYS = {
    "extracsvcolumns",
    "fulltext",
    "id",
    "rawcsv",
    "rank",
    "score",
    "thegeom",
    "timestamp",
}

FIELD_ALIASES = {
    "orgao": ("orgao", "Orgao", "Nome do Orgao", "nome_orgao", "unidade", "secretaria"),
    "modalidade": ("modalidade", "Modalidade", "tipo_modalidade", "modalidade_licitacao"),
    "numero_licitacao": (
        "numero_licitacao",
        "numero licitacao",
        "Numero_Licitacao",
        "Numero Licitacao",
        "Licitacao",
        "n_licitacao",
        "licitacao",
    ),
    "numero_processo": (
        "numero_processo",
        "Processo Administrativo",
        "processo",
        "Processo",
        "NumeroProcesso",
        "Numero_Processo",
    ),
    "numero_contrato": (
        "numero_contrato",
        "numero contrato",
        "NumeroContrato",
        "Contrato",
        "Contrato",
        "contrato",
    ),
    "objeto": ("objeto", "Objeto", "Objetivo", "descricao_objeto", "descricao", "Descricao"),
    "fornecedor": ("fornecedor", "Fornecedor", "Fornecedor e Nome de Fantasia", "contratada", "Contratada", "empresa", "Empresa"),
    "fornecedor_documento": (
        "fornecedor_documento",
        "cnpj",
        "CNPJ",
        "CNPJ CPF",
        "cpf_cnpj",
        "documento_fornecedor",
        "CNPJFornecedor",
    ),
    "valor_contrato": (
        "valor_contrato",
        "ValorContrato",
        "Valor(R$)",
        "Valor R$",
        "valor contrato",
        "valor",
        "Valor",
        "valor_total",
    ),
    "data_assinatura": (
        "data_assinatura",
        "DataAssinaturaExtrato",
        "Data da Assinatura",
        "data assinatura",
        "data_assinatura_extrato",
        "assinatura",
    ),
    "data_publicacao": (
        "data_publicacao",
        "DataPublicacaoExtrato",
        "Data da Publicacao",
        "data publicacao",
        "data_publicacao_extrato",
        "publicacao",
    ),
    "evento": ("evento", "Evento", "tipo_evento", "tipo", "situacao", "Situacao"),
    "retranca": ("retranca", "Retranca"),
}

def normalize_record(raw: Mapping[str, Any] | str, ano: int, source: str, source_system: str) -> dict[str, Any]:
    parsed = parse_record(raw)
    indexed = {normalize_key(key): value for key, value in parsed.items()}
    raw_value = dict(raw) if isinstance(raw, Mapping) else {"value": raw}
    normalized: dict[str, Any] = {
        "source": source,
        "source_system": source_system,
        "ano": ano,
        "raw": raw_value,
    }

    for field in NORMALIZED_FIELDS:
        if field in {"source", "source_system", "ano", "raw"}:
            continue
        normalized[field] = first_value(indexed, FIELD_ALIASES.get(field, (field,)))

    return normalized


def normalize_records(records: list[Mapping[str, Any] | str], ano: int, source: str, source_system: str) -> list[dict[str, Any]]:
    return [
        normalize_record(record, ano=ano, source=source, source_system=source_system)
        for raw_record in records
        for record in expand_record(raw_record)
    ]


def detect_record_format(record: Mapping[str, Any] | str) -> str:
    if isinstance(record, str):
        if "\n" in record and looks_like_csv(record):
            return "csv"
        if looks_like_csv(record):
            return "single_field_csv"
        return "other"

    non_id_items = [
        (key, value)
        for key, value in record.items()
        if normalize_key(key) not in PARSER_METADATA_KEYS
    ]
    if len(non_id_items) == 1 and isinstance(non_id_items[0][1], str) and "\n" in non_id_items[0][1] and looks_like_csv(non_id_items[0][1]):
        return "csv_embedded_json"
    if len(non_id_items) == 1 and isinstance(non_id_items[0][1], str) and looks_like_csv(non_id_items[0][1]):
        return "single_field_csv"
    sparse_csv = sparse_single_csv_value(non_id_items)
    if sparse_csv:
        return "csv_embedded_json" if "\n" in sparse_csv else "single_field_csv"
    if record_has_expected_fields(record):
        return "json_structured"
    if any(isinstance(value, str) and "\n" in value and looks_like_csv(value) for _, value in non_id_items):
        return "csv_embedded_json"
    return "json_structured" if len(record) > 1 else "other"


def parse_record(record: Mapping[str, Any] | str) -> dict[str, Any]:
    detected = detect_record_format(record)
    if detected == "json_structured" and isinstance(record, Mapping):
        return dict(record)
    if detected == "single_field_csv" and isinstance(record, Mapping):
        csv_text = first_csv_value(record)
        parsed = parse_csv_row(csv_text)
        parsed["_raw_csv"] = csv_text
        return parsed
    if detected == "single_field_csv" and isinstance(record, str):
        parsed = parse_csv_row(record)
        parsed["_raw_csv"] = record
        return parsed
    if detected in {"csv", "csv_embedded_json"}:
        csv_text = record if isinstance(record, str) else first_csv_value(record)
        rows = parse_csv_text(csv_text)
        parsed = rows[0] if rows else {}
        parsed["_raw_csv"] = csv_text
        return parsed
    return dict(record) if isinstance(record, Mapping) else {"value": record}


def expand_record(record: Mapping[str, Any] | str) -> list[dict[str, Any] | str]:
    detected = detect_record_format(record)
    if detected in {"csv", "csv_embedded_json"}:
        csv_text = record if isinstance(record, str) else first_csv_value(record)
        rows = parse_csv_text(csv_text)
        for row in rows:
            row["_raw_csv"] = csv_text
        return rows or [parse_record(record)]
    return [record]


def parse_csv_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return parse_csv_text(value)
    if isinstance(value, list):
        return [parse_record(item) if isinstance(item, (Mapping, str)) else {"value": item} for item in value]
    if isinstance(value, Mapping):
        return [parse_record(value)]
    return []


def parse_csv_text(value: str) -> list[dict[str, Any]]:
    rows = read_csv_rows(value)
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return []

    if has_header_row(rows[0]):
        headers = [cell.strip() for cell in rows[0]]
        data_rows = rows[1:]
    else:
        headers = select_fallback_headers(rows[0])
        data_rows = rows

    return [row_to_dict(headers, row) for row in data_rows]


def parse_csv_row(value: str) -> dict[str, Any]:
    rows = parse_csv_text(value)
    return rows[0] if rows else {}


def row_to_dict(headers: list[str], row: list[str]) -> dict[str, Any]:
    parsed = {headers[index]: clean_csv_cell(cell) for index, cell in enumerate(row) if index < len(headers)}
    if len(row) > len(headers):
        parsed["_extra_csv_columns"] = [clean_csv_cell(cell) for cell in row[len(headers):]]
    return parsed


def select_fallback_headers(row: list[str]) -> list[str]:
    if looks_like_e_negocios_row(row):
        return list(E_NEGOCIOS_CSV_COLUMNS[: len(row)])
    return list(FALLBACK_CSV_COLUMNS[: len(row)])


def looks_like_e_negocios_row(row: list[str]) -> bool:
    if len(row) < len(E_NEGOCIOS_CSV_COLUMNS):
        return False
    return normalize_key(row[9]) in {"pf", "pj"} or normalize_key(row[5]).startswith("extrato")


def clean_csv_cell(value: Any) -> str:
    return str(value).strip().strip(";").strip()


def has_header_row(row: list[str]) -> bool:
    normalized = {normalize_key(cell) for cell in row}
    return bool(normalized & EXPECTED_SOURCE_FIELD_KEYS)


def looks_like_csv(value: str) -> bool:
    if not value or not any(delimiter in value for delimiter in (",", ";", "|", "\t")):
        return False
    try:
        rows = read_csv_rows(value)
    except csv.Error:
        return False
    rows = [row for row in rows[:2] if any(cell.strip() for cell in row)]
    if not rows or len(rows[0]) <= 1:
        return False
    if has_header_row(rows[0]):
        return True
    return len(rows[0]) >= 4 or (len(rows) > 1 and len(rows[1]) >= 4)


def read_csv_rows(value: str) -> list[list[str]]:
    sample = value[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(value.splitlines(), dialect))


def first_csv_value(record: Mapping[str, Any]) -> str:
    for key, value in record.items():
        normalized_key = normalize_key(key)
        if normalized_key in PARSER_METADATA_KEYS:
            continue
        if isinstance(value, str) and looks_like_csv(value):
            return value
    return ""


def sparse_single_csv_value(items: list[tuple[Any, Any]]) -> str | None:
    non_empty = [(key, value) for key, value in items if not is_empty_value(value)]
    if len(non_empty) != 1:
        return None

    key, value = non_empty[0]
    if not isinstance(value, str) or not looks_like_csv(value):
        return None
    if normalize_key(key) not in CSV_CONTAINER_FIELD_KEYS:
        return None
    return value


def is_empty_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


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
