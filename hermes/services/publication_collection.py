from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from hermes.connectors.publications.hashing import build_source_code, normalize_url
from hermes.connectors.publications.normalizer import normalize_publication
from hermes.connectors.publications.source_inspector import inspect_source
from hermes.database.models import PublicSource, Publication, Source
from hermes.database.session import SessionLocal


def inspect_and_store_source(
    url: str,
    *,
    session: Session | None = None,
    probe_endpoints: bool = False,
) -> dict[str, Any]:
    owns_session = session is None
    active_session = session or SessionLocal()
    try:
        inspection = inspect_source(url, probe_endpoints=probe_endpoints)
        source = upsert_source(active_session, inspection)
        public_source = upsert_public_source(active_session, inspection, source)
        active_session.commit()
        return {
            "inspection": inspection,
            "source_id": source.id,
            "public_source_id": public_source.id,
        }
    except Exception:
        active_session.rollback()
        raise
    finally:
        if owns_session:
            active_session.close()


def collect_publications_from_source(
    url: str,
    *,
    session: Session | None = None,
    limit: int = 100,
    dry_run: bool = False,
    probe_endpoints: bool = False,
) -> dict[str, Any]:
    owns_session = session is None
    active_session = session or SessionLocal()
    summary = {"url": url, "fetched": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": []}
    try:
        inspection = inspect_source(url, probe_endpoints=probe_endpoints)
        source = upsert_source(active_session, inspection)
        public_source = upsert_public_source(active_session, inspection, source)
        candidates = inspection.get("publication_candidates", [])[:limit]
        summary["fetched"] = len(candidates)
        if dry_run:
            summary["skipped"] = len(candidates)
            summary["inspection"] = inspection
            active_session.rollback()
            return summary
        active_session.commit()
        for candidate in candidates:
            try:
                normalized = normalize_publication(candidate, source_url=inspection["url"], source_name=inspection.get("title"))
                action = upsert_publication(active_session, source, normalized)
                summary[action] += 1
                active_session.commit()
            except Exception as exc:
                active_session.rollback()
                summary["errors"].append(f"{exc.__class__.__name__}: {exc}")
        summary["public_source_id"] = public_source.id
        summary["source_id"] = source.id
        return summary
    except Exception as exc:
        active_session.rollback()
        summary["errors"].append(f"{exc.__class__.__name__}: {exc}")
        return summary
    finally:
        if owns_session:
            active_session.close()


def upsert_source(session: Session, inspection: dict[str, Any]) -> Source:
    url = inspection.get("url") or inspection.get("requested_url")
    code = build_source_code(str(url))
    source = session.scalar(select(Source).where(Source.code == code))
    if source is None:
        source = Source(
            code=code,
            name=inspection.get("title") or str(url),
            api_name="publications_scraper",
            base_url=str(url),
            scope="publications",
            metadata_json={"source": "publications_scraper"},
        )
        session.add(source)
        session.flush()
        return source
    source.name = inspection.get("title") or source.name
    source.base_url = str(url)
    source.api_name = source.api_name or "publications_scraper"
    source.scope = source.scope or "publications"
    return source


def upsert_public_source(session: Session, inspection: dict[str, Any], source: Source) -> PublicSource:
    normalized = normalize_url(str(inspection.get("url") or inspection.get("requested_url")))
    public_source = session.scalar(select(PublicSource).where(PublicSource.normalized_url == normalized))
    values = {
        "source_id": source.id,
        "url": str(inspection.get("requested_url") or inspection.get("url")),
        "normalized_url": normalized,
        "title": inspection.get("title"),
        "source_type": "official_site",
        "status": "active" if inspection.get("ok") else "error",
        "last_status_code": inspection.get("status_code"),
        "content_type": inspection.get("content_type"),
        "detected_links": inspection.get("links", [])[:200],
        "detected_endpoints": inspection.get("endpoint_candidates", [])[:100],
        "metadata_json": {
            "pdf_count": len(inspection.get("pdf_links", [])),
            "publication_candidate_count": len(inspection.get("publication_candidates", [])),
            "error": inspection.get("error"),
        },
        "last_inspected_at": datetime.now(UTC),
    }
    if public_source is None:
        public_source = PublicSource(**values)
        session.add(public_source)
        session.flush()
        return public_source
    for key, value in values.items():
        setattr(public_source, key, value)
    session.flush()
    return public_source


def upsert_publication(session: Session, source: Source, normalized: dict[str, Any]) -> str:
    existing = session.scalar(
        select(Publication).where(
            Publication.source_id == source.id,
            Publication.content_hash == normalized["content_hash"],
        )
    )
    values = publication_values(source, normalized)
    if existing is None:
        session.add(Publication(**values))
        session.flush()
        return "inserted"
    changed = False
    for key, value in values.items():
        if key == "source_id":
            continue
        if getattr(existing, key) != value:
            setattr(existing, key, value)
            changed = True
    session.flush()
    return "updated" if changed else "skipped"


def publication_values(source: Source, normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source.id,
        "external_id": normalized.get("url") or normalized["content_hash"],
        "source_name": source.name,
        "api_name": "publications_scraper",
        "publication_type": normalized.get("publication_type"),
        "object_description": normalized.get("title") or normalized.get("summary"),
        "year": normalized.get("year"),
        "published_at": parse_iso_datetime(normalized.get("published_at")),
        "links": normalized.get("links") or [],
        "raw_payload": normalized.get("raw") or {},
        "normalized_payload": normalized,
        "raw_text": normalized.get("text"),
        "clean_text": normalized.get("summary") or normalized.get("text"),
        "content_hash": normalized["content_hash"],
        "tags": ["publicacao-oficial"],
        "keywords": [],
        "classification": {"source": "publications_scraper"},
    }


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
