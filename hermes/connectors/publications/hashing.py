from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_source_code(url: str) -> str:
    return f"public-{stable_hash(normalize_url(url))[:16]}"


def build_publication_hash(record: dict[str, Any]) -> str:
    identity = {
        "source_url": normalize_url(str(record.get("source_url") or "")),
        "url": normalize_url(str(record.get("url") or "")) if record.get("url") else None,
        "title": clean_identity_text(record.get("title")),
        "published_at": record.get("published_at"),
        "publication_type": record.get("publication_type"),
        "text": clean_identity_text(record.get("text") or record.get("summary")),
    }
    return stable_hash(identity)


def clean_identity_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return " ".join(str(value).split())[:500]
