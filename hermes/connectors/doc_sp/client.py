from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import httpx

from hermes.connectors.doc_sp.auth import ApilibToken, safe_preview

DEFAULT_BASE_URLS = (
    "https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1",
    "http://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1",
    "https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1/",
    "https://servicos.imprensaoficial.com.br/pubnetRestFul",
    "https://servicos.imprensaoficial.com.br/pubnetRestFul/api",
    "https://servicos.imprensaoficial.com.br/pubnetRestFul/api/v1",
)

DEFAULT_PATHS = (
    "/swagger.json",
    "/Publicacao",
    "/Licitacao",
    "/publicacao",
    "/licitacao",
    "/api/Publicacao",
    "/api/Licitacao",
)

DEFAULT_DATES = ("2020-09-01", "2026-07-03")
DEFAULT_CADERNOS = (11,)


@dataclass(slots=True)
class DocSpRequest:
    base_url: str
    path: str
    url: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocSpResponseProbe:
    request: DocSpRequest
    status_code: int | None
    content_type: str | None
    preview: str
    elapsed_ms: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300


class DocSpClient:
    def __init__(self, token: ApilibToken, timeout_seconds: float = 30.0) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds

    def probe(
        self,
        base_urls: tuple[str, ...] = DEFAULT_BASE_URLS,
        paths: tuple[str, ...] = DEFAULT_PATHS,
        dates: tuple[str, ...] = DEFAULT_DATES,
        cadernos: tuple[int, ...] = DEFAULT_CADERNOS,
    ) -> list[DocSpResponseProbe]:
        results: list[DocSpResponseProbe] = []

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for base_url in base_urls:
                for path in paths:
                    if is_swagger_path(path):
                        results.append(self._get(client, base_url, path, params={}))
                        continue

                    for data_publicacao in dates:
                        for caderno in cadernos:
                            results.append(
                                self._get(
                                    client,
                                    base_url,
                                    path,
                                    params={"dataPublicacao": data_publicacao, "caderno": caderno},
                                )
                            )

        return results

    def _get(self, client: httpx.Client, base_url: str, path: str, params: dict[str, Any]) -> DocSpResponseProbe:
        url = build_url(base_url, path)
        request = DocSpRequest(base_url=base_url, path=path, url=url, params=params)
        started = perf_counter()

        try:
            response = client.get(
                url,
                params=params,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Authorization": self.token.authorization_header,
                },
            )
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return DocSpResponseProbe(
                request=request,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                preview=safe_preview(response.text),
                elapsed_ms=elapsed_ms,
            )
        except httpx.HTTPError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return DocSpResponseProbe(
                request=request,
                status_code=None,
                content_type=None,
                preview="",
                elapsed_ms=elapsed_ms,
                error=f"{exc.__class__.__name__}: {exc}",
            )


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def is_swagger_path(path: str) -> bool:
    return path.rstrip("/").lower().endswith("swagger.json")

