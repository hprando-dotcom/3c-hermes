from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hermes.connectors.doc_sp.auth import ApilibToken
from hermes.connectors.pmsp.licitacoes.apilib import ApilibLicitacoesClient, ApilibLicitacoesResult
from hermes.connectors.pmsp.licitacoes.dados_abertos import CkanLicitacoesResult, DadosAbertosLicitacoesClient


@dataclass(slots=True)
class ProviderError:
    source: str
    message: str
    status_code: int | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "message": self.message,
            "status_code": self.status_code,
        }


@dataclass(slots=True)
class PmspLicitacoesProviderResult:
    ano: int
    source_used: str | None
    source_system: str | None
    total: int | None
    record_count: int
    records: list[dict[str, Any]] = field(default_factory=list)
    apilib: dict[str, Any] | None = None
    ckan: dict[str, Any] | None = None
    errors: list[ProviderError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.source_used is not None and not self.errors_for_selected_source()

    @property
    def status_code(self) -> int | None:
        selected = self.selected_attempt_summary()
        if selected:
            return selected.get("status_code")
        return None

    def errors_for_selected_source(self) -> list[ProviderError]:
        if not self.source_used:
            return self.errors
        return [error for error in self.errors if error.source == self.source_used]

    def selected_attempt_summary(self) -> dict[str, Any] | None:
        if self.source_used == "apilib":
            return self.apilib
        if self.source_used == "ckan":
            return self.ckan or self.apilib
        return None

    def to_summary(self, include_records: bool = False) -> dict[str, Any]:
        summary = {
            "ano": self.ano,
            "source_used": self.source_used,
            "source_system": self.source_system,
            "status_code": self.status_code,
            "total": self.total,
            "record_count": self.record_count,
            "ok": self.ok,
            "apilib": self.apilib,
            "ckan": self.ckan,
            "errors": [error.to_summary() for error in self.errors],
        }
        if include_records:
            summary["records"] = self.records
        return summary


class PmspLicitacoesProvider:
    def __init__(
        self,
        token: ApilibToken | None = None,
        apilib_client: ApilibLicitacoesClient | None = None,
        ckan_client: DadosAbertosLicitacoesClient | None = None,
    ) -> None:
        self.token = token
        self.apilib_client = apilib_client
        self.ckan_client = ckan_client or DadosAbertosLicitacoesClient()

    def list_by_year(self, ano: int, limite: int = 100, offset: int = 0) -> PmspLicitacoesProviderResult:
        errors: list[ProviderError] = []
        apilib_result = self._try_apilib(ano, limite, offset)
        apilib_summary = apilib_result.to_summary(include_records=False) if apilib_result else None

        if apilib_result and apilib_result.ok and not apilib_result.should_fallback:
            return PmspLicitacoesProviderResult(
                ano=ano,
                source_used=apilib_result.source,
                source_system=apilib_result.source_system,
                total=apilib_result.total,
                record_count=apilib_result.record_count,
                records=apilib_result.records,
                apilib=apilib_summary,
                ckan=None,
                errors=errors,
            )

        if apilib_result is None:
            errors.append(ProviderError(source="apilib", message="APILIB token/client not configured."))
        else:
            errors.append(
                ProviderError(
                    source="apilib",
                    message=apilib_result.error or f"APILIB returned status {apilib_result.status_code}.",
                    status_code=apilib_result.status_code,
                )
            )

        ckan_result = self.ckan_client.list_by_year(ano, limite=limite, offset=offset)
        ckan_summary = ckan_result.to_summary(include_records=False)
        if ckan_result.ok:
            return PmspLicitacoesProviderResult(
                ano=ano,
                source_used="ckan",
                source_system=ckan_result.source_system,
                total=ckan_result.total,
                record_count=ckan_result.record_count,
                records=ckan_result.records,
                apilib=apilib_summary,
                ckan=ckan_summary,
                errors=errors,
            )

        errors.append(
            ProviderError(
                source="ckan",
                message=ckan_result.error or f"CKAN returned status {ckan_result.status_code}.",
                status_code=ckan_result.status_code,
            )
        )
        return PmspLicitacoesProviderResult(
            ano=ano,
            source_used=None,
            source_system=None,
            total=None,
            record_count=0,
            records=[],
            apilib=apilib_summary,
            ckan=ckan_summary,
            errors=errors,
        )

    def _try_apilib(self, ano: int, limite: int, offset: int) -> ApilibLicitacoesResult | None:
        client = self.apilib_client
        if client is None and self.token is not None:
            client = ApilibLicitacoesClient(self.token)
        if client is None:
            return None
        return client.list_by_year(ano, limite=limite, offset=offset)
