from __future__ import annotations

from hermes.connectors.publications.endpoint_scraper import detect_endpoint_candidates
from hermes.connectors.publications.hashing import build_publication_hash
from hermes.connectors.publications.html_scraper import extract_links, extract_publication_candidates
from hermes.connectors.publications.normalizer import normalize_publication
from hermes.connectors.publications.source_inspector import inspect_source_html
from hermes.database.models import Publication, Source
from hermes.services.publication_collection import publication_values, upsert_publication


FAKE_HTML = """
<!doctype html>
<html>
  <head>
    <title>Portal Oficial de Publicacoes</title>
    <link rel="alternate" href="/api/publicacoes">
    <script>const api = "/openapi.json";</script>
  </head>
  <body>
    <a href="/diario-oficial/edital-001-2026.pdf">Edital de obras 001/2026</a>
    <a href="/noticias/comunicado">Comunicado comum</a>
    <a href="https://dados.exemplo.gov.br/api/publicacoes">API Publicacoes</a>
  </body>
</html>
"""


def test_source_inspection_with_fake_html_detects_publications() -> None:
    result = inspect_source_html(FAKE_HTML, "https://www.exemplo.gov.br/publicacoes")

    assert result["ok"] is True
    assert result["title"] == "Portal Oficial de Publicacoes"
    assert len(result["links"]) == 3
    assert len(result["pdf_links"]) == 1
    assert any(item["title"] == "Edital de obras 001/2026" for item in result["publication_candidates"])


def test_html_scraper_extracts_links_and_detects_pdf() -> None:
    links = extract_links(FAKE_HTML, "https://www.exemplo.gov.br/publicacoes")

    pdf = next(item for item in links if item["is_pdf"])

    assert pdf["url"] == "https://www.exemplo.gov.br/diario-oficial/edital-001-2026.pdf"
    assert pdf["looks_like_publication"] is True


def test_endpoint_detection_finds_html_and_common_candidates() -> None:
    endpoints = detect_endpoint_candidates(FAKE_HTML, "https://www.exemplo.gov.br/publicacoes")
    urls = {item["url"] for item in endpoints}

    assert "https://www.exemplo.gov.br/openapi.json" in urls
    assert "https://dados.exemplo.gov.br/api/publicacoes" in urls
    assert "https://www.exemplo.gov.br/api" in urls


def test_publication_candidates_are_normalized() -> None:
    raw = extract_publication_candidates(FAKE_HTML, "https://www.exemplo.gov.br/publicacoes")[0]
    record = normalize_publication(raw, source_url="https://www.exemplo.gov.br/publicacoes", source_name="Portal")

    assert record["publication_type"] == "pdf"
    assert record["year"] == 2026
    assert record["title"] == "Edital de obras 001/2026"
    assert record["content_hash"]
    assert record["links"][0]["url"].endswith("edital-001-2026.pdf")


def test_publication_hash_is_stable_for_duplicate_records() -> None:
    record_a = {
        "source_url": "https://www.exemplo.gov.br/publicacoes/",
        "url": "https://www.exemplo.gov.br/edital.pdf",
        "title": "Edital 1",
        "publication_type": "pdf",
        "text": "Edital 1",
    }
    record_b = {
        "text": "Edital 1",
        "publication_type": "pdf",
        "title": "Edital 1",
        "url": "https://www.exemplo.gov.br/edital.pdf",
        "source_url": "https://www.exemplo.gov.br/publicacoes",
    }

    assert build_publication_hash(record_a) == build_publication_hash(record_b)


def test_upsert_publication_skips_existing_hash() -> None:
    source = Source(id=1, code="public-test", name="Fonte Teste")
    normalized = normalize_publication(
        {
            "url": "https://www.exemplo.gov.br/edital.pdf",
            "title": "Edital 1",
            "text": "Edital 1",
            "publication_type": "pdf",
        },
        source_url="https://www.exemplo.gov.br/publicacoes",
        source_name="Fonte Teste",
    )
    existing = Publication(**publication_values(source, normalized))
    session = FakeSession(existing)

    result = upsert_publication(session, source, normalized)

    assert result == "skipped"
    assert session.added == []
    assert session.flushed is True


class FakeSession:
    def __init__(self, existing):
        self.existing = existing
        self.added = []
        self.flushed = False

    def scalar(self, _statement):
        return self.existing

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flushed = True
