from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from hermes.connectors.publications.endpoint_scraper import detect_endpoint_candidates, probe_endpoint
from hermes.connectors.publications.hashing import normalize_url
from hermes.connectors.publications.html_scraper import (
    extract_links,
    extract_publication_candidates,
    extract_title,
    extract_visible_text,
)


def inspect_source(url: str, *, timeout_seconds: float = 20.0, probe_endpoints: bool = False) -> dict[str, Any]:
    normalized_url = normalize_url(url)
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(normalized_url, headers={"Accept": "text/html,application/xhtml+xml,application/json;q=0.8", "User-Agent": "HERMES/0.1"})
        content_type = response.headers.get("content-type", "")
        html = response.text or ""
        result = inspect_source_html(
            html,
            str(response.url),
            status_code=response.status_code,
            content_type=content_type,
            probe_endpoints=probe_endpoints,
        )
        result["requested_url"] = normalized_url
        return result
    except httpx.HTTPError as exc:
        return {
            "url": normalized_url,
            "requested_url": normalized_url,
            "ok": False,
            "status_code": None,
            "content_type": None,
            "title": None,
            "links": [],
            "pdf_links": [],
            "publication_candidates": [],
            "endpoint_candidates": [],
            "endpoint_probes": [],
            "visible_text_preview": "",
            "inspected_at": datetime.now(UTC).isoformat(),
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def inspect_source_html(
    html: str,
    base_url: str,
    *,
    status_code: int | None = 200,
    content_type: str | None = "text/html",
    probe_endpoints: bool = False,
) -> dict[str, Any]:
    links = extract_links(html, base_url)
    endpoint_candidates = detect_endpoint_candidates(html, base_url)
    endpoint_probes = [probe_endpoint(item["url"]) for item in endpoint_candidates[:5]] if probe_endpoints else []
    publication_candidates = extract_publication_candidates(html, base_url)
    return {
        "url": normalize_url(base_url),
        "requested_url": normalize_url(base_url),
        "ok": bool(status_code and 200 <= status_code < 400),
        "status_code": status_code,
        "content_type": content_type,
        "title": extract_title(html),
        "links": links,
        "pdf_links": [link for link in links if link["is_pdf"]],
        "publication_candidates": publication_candidates,
        "endpoint_candidates": endpoint_candidates,
        "endpoint_probes": endpoint_probes,
        "visible_text_preview": extract_visible_text(html, limit=800),
        "inspected_at": datetime.now(UTC).isoformat(),
        "error": None,
    }
