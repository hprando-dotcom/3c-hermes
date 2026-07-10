from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx

ENDPOINT_PATTERNS = (
    r"https?://[^\"'\s<>]+/(?:api|wp-json|openapi|swagger|dados|publicacoes|publications)[^\"'\s<>]*",
    r"[\"']((?:/api|/wp-json|/openapi\.json|/swagger\.json|/swagger|/api-docs|/publicacoes|/publications)[^\"']*)[\"']",
)

COMMON_ENDPOINTS = (
    "/openapi.json",
    "/swagger.json",
    "/swagger",
    "/api-docs",
    "/v3/api-docs",
    "/wp-json",
    "/api",
    "/api/publicacoes",
    "/api/publications",
    "/publicacoes.json",
)


def detect_endpoint_candidates(html: str, base_url: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in ENDPOINT_PATTERNS:
        for match in re.finditer(pattern, html or "", flags=re.IGNORECASE):
            raw = match.group(1) if match.groups() else match.group(0)
            url = urljoin(base_url, raw)
            add_candidate(candidates, seen, url, "html_reference")
    for path in COMMON_ENDPOINTS:
        add_candidate(candidates, seen, urljoin(base_url, path), "common_path")
    return candidates


def probe_endpoint(url: str, *, timeout_seconds: float = 8.0) -> dict[str, Any]:
    started_url = url
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"Accept": "application/json, text/html;q=0.8", "User-Agent": "HERMES/0.1"})
        preview = response.text[:300] if response.text else ""
        return {
            "url": str(response.url),
            "requested_url": started_url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "is_json": "json" in (response.headers.get("content-type") or "").lower(),
            "preview": preview,
        }
    except httpx.HTTPError as exc:
        return {
            "url": started_url,
            "requested_url": started_url,
            "status_code": None,
            "content_type": None,
            "is_json": False,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def add_candidate(candidates: list[dict[str, Any]], seen: set[str], url: str, reason: str) -> None:
    key = url.split("#", 1)[0]
    if key in seen:
        return
    seen.add(key)
    candidates.append({"url": key, "reason": reason})
