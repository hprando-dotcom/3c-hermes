from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Mapping

import httpx

from hermes.connectors.doc_sp.auth import ApilibToken, safe_preview
from hermes.connectors.pmsp.licitacoes.normalizer import normalize_records

APILIB_LICITACOES_BASE_URL = "https://gateway.apilib.prefeitura.sp.gov.br/sg/licitacoes/v1"
APILIB_SOURCE = "apilib"
APILIB_SOURCE_SYSTEM = "APILIB PMSP Licitacoes"
MIN_YEAR = 2005
MAX_YEAR = 2019


@dataclass(slots=True)
class ApilibLicitacoesResult:
    source: str
    source_system: str
    ano: int
    url: str
    params: dict[str, Any]
    status_code: int | None
    content_type: str | None
    elapsed_ms: float
    response_size: int
    preview: str
    looks_json: bool
    total: int | None
    record_count: int
    records: list[dict[str, Any]] = field(default_factory=list)
    raw_payload: Any | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    @property
    def should_fallback(self) -> bool:
        return not self.ok or self.status_code == 404 or self.status_code >= 500

    def to_summary(self, include_records: bool = False) -> dict[str, Any]:
        summary = {
            "source": self.source,
            "source_system": self.source_system,
            "ano": self.ano,
            "url": self.url,
            "params": self.params,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "elapsed_ms": self.elapsed_ms,
            "response_size": self.response_size,
            "preview": self.preview,
            "looks_json": self.looks_json,
            "total": self.total,
            "record_count": self.record_count,
            "ok": self.ok,
            "should_fallback": self.should_fallback,
            "error": self.error,
        }
        if include_records:
            summary["records"] = self.records
        return summary


class ApilibLicitacoesClient:
    def __init__(
        self,
        token: ApilibToken,
        base_url: str = APILIB_LICITACOES_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.token = token
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def list_by_year(self, ano: int, limite: int = 100, offset: int = 0) -> ApilibLicitacoesResult:
        validate_year(ano)
        params = {"limite": limite, "offset": offset}
        url = build_year_url(self.base_url, ano)
        started = perf_counter()

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=self._headers())

            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            body = response.text if response.content else ""
            payload = parse_json_or_none(response, body)
            raw_records = extract_records(payload)
            records = normalize_records(raw_records, ano=ano, source=APILIB_SOURCE, source_system=APILIB_SOURCE_SYSTEM)
            return ApilibLicitacoesResult(
                source=APILIB_SOURCE,
                source_system=APILIB_SOURCE_SYSTEM,
                ano=ano,
                url=str(response.url),
                params=params,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                elapsed_ms=elapsed_ms,
                response_size=len(response.content),
                preview=safe_preview(body),
                looks_json=payload is not None or has_json_content_type(response),
                total=extract_total(payload, raw_records),
                record_count=len(records),
                records=records,
                raw_payload=payload,
            )
        except httpx.HTTPError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return ApilibLicitacoesResult(
                source=APILIB_SOURCE,
                source_system=APILIB_SOURCE_SYSTEM,
                ano=ano,
                url=url,
                params=params,
                status_code=None,
                content_type=None,
                elapsed_ms=elapsed_ms,
                response_size=0,
                preview="",
                looks_json=False,
                total=None,
                record_count=0,
                error=f"{exc.__class__.__name__}: {exc}",
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.token.authorization_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


def validate_year(ano: int) -> None:
    if ano < MIN_YEAR or ano > MAX_YEAR:
        raise ValueError(f"ano must be between {MIN_YEAR} and {MAX_YEAR}: {ano}")


def build_year_url(base_url: str, ano: int) -> str:
    return f"{base_url.rstrip('/')}/{ano}"


def has_json_content_type(response: httpx.Response) -> bool:
    return "json" in response.headers.get("content-type", "").lower()


def parse_json_or_none(response: httpx.Response, body: str) -> Any | None:
    if not body.strip():
        return None
    if not has_json_content_type(response) and not body.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def extract_records(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, dict):
        return []

    result = payload.get("result")
    if isinstance(result, dict):
        records = result.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, Mapping)]

    for key in ("records", "data", "items", "results", "resultados", "licitacoes", "content"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]

    return []


def extract_total(payload: Any, records: list[Mapping[str, Any]]) -> int | None:
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, dict):
            total = result.get("total")
            if isinstance(total, int):
                return total
        for key in ("total", "count"):
            total = payload.get(key)
            if isinstance(total, int):
                return total
    return len(records) if records else None
