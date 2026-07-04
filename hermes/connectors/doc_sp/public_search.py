from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

import httpx

PUBLIC_SEARCH_URL = "https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php"
PUBLIC_SEARCH_ACTION = "materias_pesquisar"


@dataclass(slots=True)
class PublicSearchPage:
    url: str
    params: dict[str, Any]
    status_code: int
    content_type: str | None
    html: str


@dataclass(slots=True)
class PublicSearchResult:
    publication_id: str | None = None
    title: str | None = None
    published_on: str | None = None
    section: str | None = None
    url: str | None = None
    text_preview: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class DocSpPublicSearchConnector:
    """Initial fallback connector for the public DOC-SP search page.

    This class intentionally stops before full scraping. The current scope is to
    centralize the public endpoint, request shape, and normalization contract so
    the future collector can add HTML selectors without touching scheduler or
    ingestion boundaries.
    """

    def __init__(self, base_url: str = PUBLIC_SEARCH_URL, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def search_by_date(self, published_on: date | str) -> list[PublicSearchResult]:
        """Fetch the public search page for a publication date.

        The parser is not implemented in this sprint. Until selectors are mapped
        against the live page, this method returns an empty list after a
        successful HTTP request.
        """

        params = {
            "acao": PUBLIC_SEARCH_ACTION,
            "data_publicacao": normalize_date(published_on),
        }
        page = self._request_search(params)
        return [self.normalize_result(raw_result) for raw_result in self._extract_raw_results(page)]

    def search_by_keyword(self, keyword: str, published_on: date | str | None = None) -> list[PublicSearchResult]:
        """Fetch the public search page for a keyword and optional date."""

        params: dict[str, Any] = {
            "acao": PUBLIC_SEARCH_ACTION,
            "palavra_chave": keyword,
        }
        if published_on is not None:
            params["data_publicacao"] = normalize_date(published_on)

        page = self._request_search(params)
        return [self.normalize_result(raw_result) for raw_result in self._extract_raw_results(page)]

    def fetch_publication(self, publication_url: str) -> PublicSearchPage:
        """Fetch a publication detail page by URL.

        Future scraping should parse the returned HTML into the publication raw
        text, source metadata, and downloadable attachments when available.
        """

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(publication_url, headers={"Accept": "text/html,application/xhtml+xml"})
            response.raise_for_status()

        return PublicSearchPage(
            url=str(response.url),
            params={},
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            html=response.text,
        )

    def normalize_result(self, raw_result: Mapping[str, Any]) -> PublicSearchResult:
        """Normalize one parsed search result into the HERMES fallback shape."""

        raw = dict(raw_result)
        return PublicSearchResult(
            publication_id=optional_str(first_present(raw, "id", "publication_id", "codigo")),
            title=optional_str(first_present(raw, "title", "titulo", "materia")),
            published_on=optional_str(first_present(raw, "published_on", "data_publicacao", "data")),
            section=optional_str(first_present(raw, "section", "secao", "caderno")),
            url=optional_str(first_present(raw, "url", "link", "href")),
            text_preview=optional_str(first_present(raw, "text_preview", "resumo", "ementa")),
            raw=raw,
        )

    def _request_search(self, params: dict[str, Any]) -> PublicSearchPage:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                self.base_url,
                params=params,
                headers={"Accept": "text/html,application/xhtml+xml"},
            )
            response.raise_for_status()

        return PublicSearchPage(
            url=str(response.url),
            params=params,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            html=response.text,
        )

    def _extract_raw_results(self, page: PublicSearchPage) -> list[dict[str, Any]]:
        # HTML selectors are intentionally pending until the next scraping sprint.
        _ = page
        return []


def normalize_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value


def first_present(raw: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return None


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
