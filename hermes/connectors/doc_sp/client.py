from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import httpx

from hermes.connectors.doc_sp.auth import ApilibToken, safe_preview

APILIB_GATEWAY_URL = "https://gateway.apilib.prefeitura.sp.gov.br"

DEFAULT_API_STORE_URLS = (
    "https://apilib.prefeitura.sp.gov.br/store/api-docs/admin/Diario_Oficial/v1",
    "https://apilib.prefeitura.sp.gov.br/store/apis/info?name=Diario_Oficial&provider=admin&version=v1",
    "https://apilib.prefeitura.sp.gov.br/store/api-docs?name=Diario_Oficial&provider=admin&version=v1",
    "https://apilib.prefeitura.sp.gov.br/store/api-docs/admin/Diario_Oficial/v1/swagger.json",
)

DEFAULT_BASE_PATHS = (
    "/Diario_Oficial/v1",
    "/diario_oficial/v1",
    "/diario-oficial/v1",
    "/dom/v1",
    "/sgdom/v1",
    "/sg/dom/v1",
    "/SG/DOM/v1",
    "/SG_DOM/v1",
)

DEFAULT_BASE_URLS = tuple(f"{APILIB_GATEWAY_URL}{base_path}" for base_path in DEFAULT_BASE_PATHS)

DEFAULT_ENDPOINT_PATHS = (
    "/Publicacao",
    "/Licitacao",
)

DEFAULT_SWAGGER_PATHS = (
    "/swagger.json",
)

DEFAULT_DATES = ("2020-09-01", "2026-07-03")
DEFAULT_CADERNOS = (11, "11")


@dataclass(frozen=True, slots=True)
class HeaderProfile:
    name: str
    headers: dict[str, str]


@dataclass(slots=True)
class DocSpRequest:
    base_url: str
    path: str
    url: str
    header_profile: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


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


@dataclass(slots=True)
class OpenApiDiscoveryProbe:
    url: str
    status_code: int | None
    content_type: str | None
    preview: str
    elapsed_ms: float
    error: str | None = None
    servers: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    @property
    def has_openapi(self) -> bool:
        return bool(self.servers or self.paths)


class DocSpClient:
    def __init__(self, token: ApilibToken, timeout_seconds: float = 30.0) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds

    def discover_openapi(
        self,
        urls: tuple[str, ...] = DEFAULT_API_STORE_URLS,
    ) -> list[OpenApiDiscoveryProbe]:
        results: list[OpenApiDiscoveryProbe] = []

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for url in urls:
                results.append(self._discover(client, url))

        return results

    def probe(
        self,
        base_urls: tuple[str, ...] = DEFAULT_BASE_URLS,
        endpoint_paths: tuple[str, ...] = DEFAULT_ENDPOINT_PATHS,
        swagger_paths: tuple[str, ...] = DEFAULT_SWAGGER_PATHS,
        dates: tuple[str, ...] = DEFAULT_DATES,
        cadernos: tuple[int | str, ...] = DEFAULT_CADERNOS,
    ) -> list[DocSpResponseProbe]:
        results: list[DocSpResponseProbe] = []
        header_profiles = build_header_profiles(self.token)

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for base_url in base_urls:
                for path in swagger_paths:
                    for header_profile in header_profiles:
                        results.append(self._get(client, base_url, path, params={}, header_profile=header_profile))

                for path in endpoint_paths:
                    for data_publicacao in dates:
                        for caderno in cadernos:
                            for header_profile in header_profiles:
                                results.append(
                                    self._get(
                                        client,
                                        base_url,
                                        path,
                                        params={"dataPublicacao": data_publicacao, "caderno": caderno},
                                        header_profile=header_profile,
                                    )
                                )

        return results

    def _discover(self, client: httpx.Client, url: str) -> OpenApiDiscoveryProbe:
        started = perf_counter()

        try:
            response = client.get(
                url,
                headers={
                    "Accept": "application/json, text/html, text/plain, */*",
                },
            )
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            servers, paths = extract_openapi_summary(response)
            return OpenApiDiscoveryProbe(
                url=url,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                preview=safe_preview(response.text),
                elapsed_ms=elapsed_ms,
                servers=servers,
                paths=paths,
            )
        except httpx.HTTPError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return OpenApiDiscoveryProbe(
                url=url,
                status_code=None,
                content_type=None,
                preview="",
                elapsed_ms=elapsed_ms,
                error=f"{exc.__class__.__name__}: {exc}",
            )

    def _get(
        self,
        client: httpx.Client,
        base_url: str,
        path: str,
        params: dict[str, Any],
        header_profile: HeaderProfile,
    ) -> DocSpResponseProbe:
        url = build_url(base_url, path)
        request = DocSpRequest(
            base_url=base_url,
            path=path,
            url=url,
            header_profile=header_profile.name,
            params=params,
            headers=mask_probe_headers(header_profile.headers),
        )
        started = perf_counter()

        try:
            response = client.get(
                url,
                params=params,
                headers=header_profile.headers,
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


def build_header_profiles(token: ApilibToken) -> list[HeaderProfile]:
    authorization_header = f"Bearer {token.access_token}"
    base_json_headers = {"Accept": "application/json"}
    content_json_headers = {**base_json_headers, "Content-Type": "application/json"}

    return [
        HeaderProfile(
            name="authorization_accept_json",
            headers={**base_json_headers, "Authorization": authorization_header},
        ),
        HeaderProfile(
            name="authorization_content_json",
            headers={**content_json_headers, "Authorization": authorization_header},
        ),
        HeaderProfile(
            name="apikey_accept_json",
            headers={**base_json_headers, "apikey": token.access_token},
        ),
        HeaderProfile(
            name="apikey_content_json",
            headers={**content_json_headers, "apikey": token.access_token},
        ),
        HeaderProfile(
            name="authorization_and_apikey",
            headers={**content_json_headers, "Authorization": authorization_header, "apikey": token.access_token},
        ),
    ]


def mask_probe_headers(headers: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in {"authorization", "apikey"}:
            masked[key] = "<redacted>"
        else:
            masked[key] = value
    return masked


def extract_openapi_summary(response: httpx.Response) -> tuple[list[str], list[str]]:
    try:
        payload = response.json()
    except ValueError:
        return [], []

    if not isinstance(payload, dict):
        return [], []

    servers = [
        str(server.get("url"))
        for server in payload.get("servers", [])
        if isinstance(server, dict) and server.get("url")
    ]
    paths = sorted(str(path) for path in payload.get("paths", {}).keys())
    return servers, paths
