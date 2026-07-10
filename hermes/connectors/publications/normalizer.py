from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from hermes.connectors.publications.hashing import build_publication_hash, normalize_url

DATE_PATTERNS = (
    r"(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})",
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",
)


def normalize_publication(raw: dict[str, Any], *, source_url: str, source_name: str | None = None) -> dict[str, Any]:
    url = raw.get("url") or raw.get("link") or raw.get("href")
    title = clean_text(raw.get("title") or raw.get("text") or raw.get("name") or infer_title_from_url(url))
    text = clean_text(raw.get("text") or raw.get("summary") or raw.get("description") or title)
    publication_type = raw.get("publication_type") or detect_publication_type(url, raw)
    published_at = parse_datetime(raw.get("published_at") or raw.get("date") or text or title)
    year = published_at.year if published_at else infer_year(text or title or url)
    normalized = {
        "source_url": normalize_url(source_url),
        "source_name": source_name,
        "url": normalize_url(str(url)) if url else None,
        "title": title,
        "text": text,
        "summary": text[:500] if text else title,
        "publication_type": publication_type,
        "published_at": published_at.isoformat() if published_at else None,
        "year": year,
        "links": build_links(url, raw),
        "raw": raw,
    }
    normalized["content_hash"] = build_publication_hash(normalized)
    return normalized


def detect_publication_type(url: Any, raw: dict[str, Any]) -> str:
    raw_type = str(raw.get("content_type") or raw.get("mime_type") or "").lower()
    if raw.get("is_pdf") or str(url or "").lower().split("?", 1)[0].endswith(".pdf") or "pdf" in raw_type:
        return "pdf"
    if raw.get("endpoint"):
        return "endpoint"
    return "html"


def build_links(url: Any, raw: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    if url:
        links.append(
            {
                "url": normalize_url(str(url)),
                "type": detect_publication_type(url, raw),
                "label": clean_text(raw.get("title") or raw.get("text") or "Publicacao"),
            }
        )
    for item in raw.get("links") or []:
        if isinstance(item, dict) and item.get("url"):
            links.append(item)
    return links


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or "")
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return datetime(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            continue
    return None


def infer_year(value: Any) -> int | None:
    match = re.search(r"\b(20\d{2}|19\d{2})\b", str(value or ""))
    if not match:
        return None
    return int(match.group(1))


def infer_title_from_url(url: Any) -> str | None:
    if not url:
        return None
    fragment = str(url).rstrip("/").rsplit("/", 1)[-1]
    fragment = fragment.split("?", 1)[0]
    return clean_text(fragment.replace("-", " ").replace("_", " "))


def clean_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = " ".join(str(value).split())
    return text or None
