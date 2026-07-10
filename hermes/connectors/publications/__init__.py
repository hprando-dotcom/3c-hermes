from __future__ import annotations

from hermes.connectors.publications.endpoint_scraper import detect_endpoint_candidates
from hermes.connectors.publications.hashing import build_publication_hash, normalize_url
from hermes.connectors.publications.html_scraper import extract_links, extract_publication_candidates
from hermes.connectors.publications.normalizer import normalize_publication
from hermes.connectors.publications.source_inspector import inspect_source, inspect_source_html

__all__ = [
    "build_publication_hash",
    "detect_endpoint_candidates",
    "extract_links",
    "extract_publication_candidates",
    "inspect_source",
    "inspect_source_html",
    "normalize_publication",
    "normalize_url",
]
