from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Mapping

import httpx

from hermes.connectors.doc_sp.auth import safe_preview
from hermes.connectors.pmsp.licitacoes.normalizer import (
    EXPECTED_SOURCE_FIELD_KEYS,
    normalize_key,
    normalize_records,
    record_has_expected_fields,
)

CKAN_ACTION_BASE_URL = "https://dados.prefeitura.sp.gov.br/api/action"
CKAN_SOURCE = "ckan"
CKAN_SOURCE_SYSTEM = "PMSP Dados Abertos CKAN"
DISCOVERY_QUERIES = (
    "licitacoes",
    "compras",
    "contratos",
    "e-negocios",
    "enegocios",
    "compras e licitacoes",
)
USEFUL_FORMATS = {"json", "csv", "xls", "xlsx"}


@dataclass(slots=True)
class CkanActionResult:
    action: str
    url: str
    params: dict[str, Any]
    status_code: int | None
    content_type: str | None
    elapsed_ms: float
    response_size: int
    preview: str
    looks_json: bool
    success: bool | None
    payload: Any | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    def to_summary(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "url": self.url,
            "params": self.params,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "elapsed_ms": self.elapsed_ms,
            "response_size": self.response_size,
            "preview": self.preview,
            "looks_json": self.looks_json,
            "success": self.success,
            "error": self.error,
        }


@dataclass(slots=True)
class CkanResourceCandidate:
    resource_id: str
    package_id: str | None
    name: str | None
    title: str | None
    description: str | None
    format: str | None
    url: str | None
    search_query: str
    year_hits: list[int] = field(default_factory=list)
    inspected_fields: list[str] = field(default_factory=list)
    field_hits: list[str] = field(default_factory=list)
    score: int = 0

    def to_summary(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "package_id": self.package_id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "format": self.format,
            "url": self.url,
            "search_query": self.search_query,
            "year_hits": self.year_hits,
            "inspected_fields": self.inspected_fields,
            "field_hits": self.field_hits,
            "score": self.score,
        }


@dataclass(slots=True)
class CkanLicitacoesResult:
    source: str
    source_system: str
    ano: int
    resource_id: str | None
    url: str | None
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
    selected_resource: dict[str, Any] | None = None
    discovered_resources: list[dict[str, Any]] = field(default_factory=list)
    raw_payload: Any | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    def to_summary(self, include_records: bool = False) -> dict[str, Any]:
        summary = {
            "source": self.source,
            "source_system": self.source_system,
            "ano": self.ano,
            "resource_id": self.resource_id,
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
            "selected_resource": self.selected_resource,
            "discovered_resources": self.discovered_resources,
            "error": self.error,
        }
        if include_records:
            summary["records"] = self.records
        return summary


class DadosAbertosLicitacoesClient:
    def __init__(self, base_url: str = CKAN_ACTION_BASE_URL, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self._resources_cache: list[CkanResourceCandidate] | None = None

    def package_search(self, query: str) -> CkanActionResult:
        return self._get_action("package_search", {"q": query, "rows": 10})

    def package_show(self, package_id: str) -> CkanActionResult:
        return self._get_action("package_show", {"id": package_id})

    def datastore_search(
        self,
        resource_id: str,
        limit: int,
        offset: int,
        q: str | None = None,
    ) -> CkanActionResult:
        params: dict[str, Any] = {"resource_id": resource_id, "limit": limit, "offset": offset}
        if q:
            params["q"] = q
        return self._get_action("datastore_search", params)

    def discover_resources(self) -> list[CkanResourceCandidate]:
        if self._resources_cache is not None:
            return self._resources_cache

        candidates_by_id: dict[str, CkanResourceCandidate] = {}
        for query in DISCOVERY_QUERIES:
            search = self.package_search(query)
            for package in iter_search_packages(search.payload):
                package_id = optional_str(package.get("id") or package.get("name"))
                if not package_id:
                    continue
                package_detail = self.package_show(package_id)
                package_payload = package_detail.payload if package_detail.ok and package_detail.success is not False else None
                for resource in iter_package_resources(package_payload or package):
                    candidate = build_candidate(resource, package_id=package_id, search_query=query)
                    if not candidate:
                        continue
                    existing = candidates_by_id.get(candidate.resource_id)
                    if existing is None or candidate.score > existing.score:
                        candidates_by_id[candidate.resource_id] = candidate

        candidates = list(candidates_by_id.values())
        for candidate in candidates:
            inspect_resource_fields(candidate, self)
        candidates.sort(key=lambda item: item.score, reverse=True)
        self._resources_cache = candidates
        return candidates

    def list_by_year(self, ano: int, limite: int = 100, offset: int = 0) -> CkanLicitacoesResult:
        started = perf_counter()
        resources = self.discover_resources()
        resource = select_resource_for_year(resources, ano)
        discovered = [candidate.to_summary() for candidate in resources[:20]]

        if resource is None:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return CkanLicitacoesResult(
                source=CKAN_SOURCE,
                source_system=CKAN_SOURCE_SYSTEM,
                ano=ano,
                resource_id=None,
                url=None,
                params={"limit": limite, "offset": offset},
                status_code=None,
                content_type=None,
                elapsed_ms=elapsed_ms,
                response_size=0,
                preview="",
                looks_json=False,
                total=None,
                record_count=0,
                discovered_resources=discovered,
                error=f"No CKAN resource candidate found for ano={ano}.",
            )

        response = self.datastore_search(resource.resource_id, limit=limite, offset=offset)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        raw_records = extract_records(response.payload)
        records = normalize_records(raw_records, ano=ano, source=CKAN_SOURCE, source_system=CKAN_SOURCE_SYSTEM)
        return CkanLicitacoesResult(
            source=CKAN_SOURCE,
            source_system=CKAN_SOURCE_SYSTEM,
            ano=ano,
            resource_id=resource.resource_id,
            url=response.url,
            params=response.params,
            status_code=response.status_code,
            content_type=response.content_type,
            elapsed_ms=elapsed_ms,
            response_size=response.response_size,
            preview=response.preview,
            looks_json=response.looks_json,
            total=extract_total(response.payload, raw_records),
            record_count=len(records),
            records=records,
            selected_resource=resource.to_summary(),
            discovered_resources=discovered,
            raw_payload=response.payload,
            error=response.error or ("CKAN returned success=false." if response.success is False else None),
        )

    def _get_action(self, action: str, params: dict[str, Any]) -> CkanActionResult:
        url = f"{self.base_url.rstrip('/')}/{action}"
        started = perf_counter()

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, params=params, headers={"Accept": "application/json"})
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            body = response.text if response.content else ""
            payload = parse_json_or_none(response, body)
            return CkanActionResult(
                action=action,
                url=str(response.url),
                params=params,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                elapsed_ms=elapsed_ms,
                response_size=len(response.content),
                preview=safe_preview(body),
                looks_json=payload is not None or has_json_content_type(response),
                success=extract_success(payload),
                payload=payload,
            )
        except httpx.HTTPError as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 2)
            return CkanActionResult(
                action=action,
                url=url,
                params=params,
                status_code=None,
                content_type=None,
                elapsed_ms=elapsed_ms,
                response_size=0,
                preview="",
                looks_json=False,
                success=None,
                error=f"{exc.__class__.__name__}: {exc}",
            )


def build_candidate(resource: Mapping[str, Any], package_id: str, search_query: str) -> CkanResourceCandidate | None:
    resource_id = optional_str(resource.get("id"))
    if not resource_id:
        return None

    name = optional_str(resource.get("name"))
    title = optional_str(resource.get("title"))
    description = optional_str(resource.get("description"))
    resource_format = optional_str(resource.get("format"))
    url = optional_str(resource.get("url"))
    text = " ".join(item for item in (name, title, description, resource_format, url) if item)
    score = score_resource_text(text, resource_format)
    year_hits = extract_years(text)

    if score <= 0 and not year_hits:
        return None

    return CkanResourceCandidate(
        resource_id=resource_id,
        package_id=package_id,
        name=name,
        title=title,
        description=description,
        format=resource_format,
        url=url,
        search_query=search_query,
        year_hits=year_hits,
        score=score + len(year_hits),
    )


def inspect_resource_fields(candidate: CkanResourceCandidate, client: DadosAbertosLicitacoesClient) -> None:
    probe = client.datastore_search(candidate.resource_id, limit=1, offset=0)
    payload = probe.payload
    fields = extract_fields(payload)
    candidate.inspected_fields = fields
    candidate.field_hits = [field for field in fields if normalize_key(field) in EXPECTED_SOURCE_FIELD_KEYS]
    if candidate.field_hits:
        candidate.score += 20 + len(candidate.field_hits)
    records = extract_records(payload)
    if any(isinstance(record, Mapping) and record_has_expected_fields(record) for record in records):
        candidate.score += 20


def select_resource_for_year(resources: list[CkanResourceCandidate], ano: int) -> CkanResourceCandidate | None:
    if not resources:
        return None
    with_year = [resource for resource in resources if ano in resource.year_hits]
    if with_year:
        return sorted(with_year, key=lambda item: item.score, reverse=True)[0]
    return resources[0]


def score_resource_text(text: str, resource_format: str | None) -> int:
    normalized = normalize_key(text)
    score = 0
    for keyword in ("licitacao", "licitacoes", "compra", "compras", "contrato", "contratos", "enegocios"):
        if keyword in normalized:
            score += 5
    if resource_format and normalize_key(resource_format) in USEFUL_FORMATS:
        score += 10
    return score


def extract_years(text: str) -> list[int]:
    years = sorted({int(match) for match in re.findall(r"\b20(?:0[5-9]|1[0-9])\b", text or "")})
    return [year for year in years if 2005 <= year <= 2019]


def iter_search_packages(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    results = result.get("results")
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, Mapping)]


def iter_package_resources(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result") if "result" in payload else payload
    if not isinstance(result, dict):
        return []
    resources = result.get("resources")
    if not isinstance(resources, list):
        return []
    return [item for item in resources if isinstance(item, Mapping)]


def extract_records(payload: Any) -> list[Mapping[str, Any] | str]:
    if isinstance(payload, str):
        return [payload]
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if isinstance(result, dict):
        records = result.get("records")
        if isinstance(records, str):
            return [records]
        if isinstance(records, list):
            return [item for item in records if isinstance(item, (Mapping, str))]
    return []


def extract_fields(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    fields = result.get("fields")
    if not isinstance(fields, list):
        return []
    names: list[str] = []
    for field in fields:
        if isinstance(field, Mapping) and field.get("id"):
            names.append(str(field["id"]))
    return names


def extract_total(payload: Any, records: list[Mapping[str, Any] | str]) -> int | None:
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, dict):
            total = result.get("total")
            if isinstance(total, int):
                return total
    return len(records) if records else None


def extract_success(payload: Any) -> bool | None:
    if isinstance(payload, dict) and isinstance(payload.get("success"), bool):
        return payload["success"]
    return None


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


def optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
