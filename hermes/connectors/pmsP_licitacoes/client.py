from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import httpx

from hermes.connectors.doc_sp.auth import ApilibToken, safe_preview

PMSP_LICITACOES_BASE_URL = "https://gateway.apilib.prefeitura.sp.gov.br/sg/licitacoes/v1"
MIN_YEAR = 2005
MAX_YEAR = 2019


@dataclass(slots=True)
class PmspLicitacoesRequest:
    ano: int
    url: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PmspLicitacoesResponse:
    request: PmspLicitacoesRequest
    status_code: int | None
    content_type: str | None
    elapsed_ms: float
    response_size: int
    preview: str
    looks_json: bool
    record_count: int | None
    json_payload: Any | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300


class PmspLicitacoesClient:
    def __init__(
        self,
        token: ApilibToken,
        base_url: str = PMSP_LICITACOES_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.token = token
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def list_by_year(self, ano: int, limite: int | None = None, offset: int | None = None) -> PmspLicitacoesResponse:
        validate_year(ano)
        params = build_params(limite=limite, offset=offset)
        url = build_year_url(self.base_url, ano)
        request = PmspLicitacoesRequest(ano=ano, url=url, params=params)
        started = perf_counter()

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=self._headers())

            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            body = response.text if response.content else ""
            json_payload = parse_json_or_none(response, body)
            response_request = PmspLicitacoesRequest(ano=ano, url=str(response.url), params=params)
            return PmspLicitacoesResponse(
                request=response_request,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                elapsed_ms=elapsed_ms,
                response_size=len(response.content),
                preview=safe_preview(body),
                looks_json=json_payload is not None or has_json_content_type(response),
                record_count=count_records(json_payload),
                json_payload=json_payload,
            )
        except httpx.HTTPError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return PmspLicitacoesResponse(
                request=request,
                status_code=None,
                content_type=None,
                elapsed_ms=elapsed_ms,
                response_size=0,
                preview="",
                looks_json=False,
                record_count=None,
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


def build_params(limite: int | None = None, offset: int | None = None) -> dict[str, int]:
    params: dict[str, int] = {}
    if limite is not None:
        params["limite"] = limite
    if offset is not None:
        params["offset"] = offset
    return params


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


def count_records(payload: Any) -> int | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "resultados", "licitacoes", "content"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        for value in payload.values():
            if isinstance(value, list):
                return len(value)
        return 0 if not payload else None
    return None
