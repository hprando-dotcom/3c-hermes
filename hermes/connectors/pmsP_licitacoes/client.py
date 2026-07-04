from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hermes.connectors.doc_sp.auth import ApilibToken
from hermes.connectors.pmsp.licitacoes.apilib import (
    APILIB_LICITACOES_BASE_URL as PMSP_LICITACOES_BASE_URL,
    MAX_YEAR,
    MIN_YEAR,
    ApilibLicitacoesClient,
)
from hermes.connectors.pmsp.licitacoes.provider import PmspLicitacoesProvider


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
    """Backward-compatible wrapper for the new PMSP Licitacoes provider."""

    def __init__(
        self,
        token: ApilibToken,
        base_url: str = PMSP_LICITACOES_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.token = token
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.provider = PmspLicitacoesProvider(
            token=token,
            apilib_client=ApilibLicitacoesClient(token=token, base_url=base_url, timeout_seconds=timeout_seconds),
        )

    def list_by_year(self, ano: int, limite: int | None = None, offset: int | None = None) -> PmspLicitacoesResponse:
        validate_year(ano)
        result = self.provider.list_by_year(ano, limite=limite or 100, offset=offset or 0)
        selected = result.selected_attempt_summary() or {}
        errors = "; ".join(error.message for error in result.errors) if not result.source_used else None

        return PmspLicitacoesResponse(
            request=PmspLicitacoesRequest(
                ano=ano,
                url=str(selected.get("url") or ""),
                params=dict(selected.get("params") or {}),
            ),
            status_code=selected.get("status_code"),
            content_type=selected.get("content_type"),
            elapsed_ms=float(selected.get("elapsed_ms") or 0),
            response_size=int(selected.get("response_size") or 0),
            preview=str(selected.get("preview") or ""),
            looks_json=bool(selected.get("looks_json")),
            record_count=result.record_count,
            json_payload=result.to_summary(include_records=True),
            error=errors,
        )


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
