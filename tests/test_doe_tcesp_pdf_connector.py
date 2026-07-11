from __future__ import annotations

from datetime import date
from pathlib import Path

from hermes.connectors.tcesp.doe_tcesp_pdf import (
    DoeTcespPdfConnector,
    build_doe_tcesp_pdf_url,
    extract_page_metadata,
)
from hermes.services.deepseek_service import DeepSeekService
from hermes.services.official_gazette_investigation import run_official_gazette_investigation


PAGE_46 = """
46 — 847ª edição Diário Oficial Eletrônico - TCESP Disponibilização: 09/07/2026 — Publicação: 13/07/2026
PROCESSOS: TC-008166.989.26-9, TC-008230.989.26-1, TC-008756.989.26-5.
Concorrência 90.065/2024. Relator Samy Wurman.
"""

PAGE_47 = """
47 — 847ª edição Diário Oficial Eletrônico - TCESP Disponibilização: 09/07/2026 — Publicação: 13/07/2026
Continuação: TC-008944.989.26-8, TC-009013.989.26-4, TC-009031.989.26-2, TC-009177.989.26-6.
"""

REAL_TERMS = [
    "TC-008166.989.26-9",
    "TC-008230.989.26-1",
    "TC-008756.989.26-5",
    "TC-008944.989.26-8",
    "TC-009013.989.26-4",
    "TC-009031.989.26-2",
    "TC-009177.989.26-6",
    "90.065/2024",
    "Samy Wurman",
]


def test_doe_tcesp_pdf_url_is_built_from_date() -> None:
    assert build_doe_tcesp_pdf_url(date(2026, 7, 9)) == "https://doe.tce.sp.gov.br/pdf/2026/07/doe-tce-2026-07-09.pdf"


def test_extract_page_metadata_from_footer() -> None:
    metadata = extract_page_metadata(PAGE_46, page_number=46)

    assert metadata.page_number == 46
    assert metadata.footer_page == 46
    assert metadata.edition == "847ª edição"
    assert metadata.availability_date == "09/07/2026"
    assert metadata.publication_date == "13/07/2026"


def test_connector_searches_daily_pdfs_and_returns_evidence(tmp_path: Path, monkeypatch) -> None:
    fetched_urls: list[str] = []
    connector = DoeTcespPdfConnector(raw_dir=tmp_path / "raw", fetcher=fake_doe_tcesp_fetcher(fetched_urls))
    monkeypatch.setattr(connector, "_extract_pdf_pages", lambda _content: [PAGE_46, PAGE_47])

    report = connector.search(date_start="2026-07-01", date_end="2026-07-17", terms=REAL_TERMS)

    assert "https://doe.tce.sp.gov.br/pdf/2026/07/doe-tce-2026-07-09.pdf" in fetched_urls
    assert len(report.candidates) == 17
    assert all(result.status == "encontrado" for result in report.results)

    first = next(result for result in report.results if result.term == "TC-008166.989.26-9")
    assert first.page == 46
    assert first.page_link == "https://doe.tce.sp.gov.br/pdf/2026/07/doe-tce-2026-07-09.pdf#page=46"
    assert first.edition == "847ª edição"
    assert first.availability_date == "09/07/2026"
    assert first.publication_date == "13/07/2026"
    assert "TC-008166.989.26-9" in (first.snippet or "")
    assert first.raw_pdf_path is not None
    assert Path(first.raw_pdf_path).exists()
    assert first.text_path is not None
    assert Path(first.text_path).name == "page_046.txt"
    assert Path(first.text_path).exists()

    continued = next(result for result in report.results if result.term == "TC-009177.989.26-6")
    assert continued.page == 47
    assert continued.page_link.endswith("#page=47")


def test_connector_returns_nao_encontrado_without_false_positive(tmp_path: Path, monkeypatch) -> None:
    connector = DoeTcespPdfConnector(raw_dir=tmp_path / "raw", fetcher=fake_doe_tcesp_fetcher([]))
    monkeypatch.setattr(connector, "_extract_pdf_pages", lambda _content: [PAGE_46, PAGE_47])

    report = connector.search(date_start="2026-07-09", date_end="2026-07-09", terms=["TC-999999.989.26-0"])

    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == "nao_encontrado"
    assert result.found is False
    assert result.page_link is None
    assert result.motivo == "Termo/processo nao localizado nos PDFs diarios consultados."
    assert result.pdfs_consultados == ["https://doe.tce.sp.gov.br/pdf/2026/07/doe-tce-2026-07-09.pdf"]


def test_official_investigation_uses_doe_tcesp_pdf_before_homepage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("hermes.connectors.tcesp.doe_tcesp_pdf.DoeTcespPdfConnector._extract_pdf_pages", lambda _self, _content: [PAGE_46, PAGE_47])

    report = run_official_gazette_investigation(
        "https://doe.tce.sp.gov.br/",
        "Procure os processos TC-008166.989.26-9 e TC-009177.989.26-6",
        "2026-07-01",
        "2026-07-17",
        limit=20,
        fetcher=fake_fetcher_that_rejects_homepage,
        deepseek_service=DeepSeekService(api_key=None),
        report_dir=tmp_path / "reports",
        raw_dir=tmp_path / "raw",
    )

    assert "DOE-TCESP PDF diario Evidencia-First" in report.strategy
    assert report.links_found == 0
    assert len(report.findings) == 2
    assert "#page=46" in report.markdown
    assert "#page=47" in report.markdown
    assert "847ª edição" in report.markdown
    assert "09/07/2026" in report.markdown
    assert "13/07/2026" in report.markdown
    assert "youtube" not in report.markdown.lower()
    assert "áudio" not in report.markdown.lower()
    assert Path(report.markdown_path).exists()
    assert Path(report.report_html_path).exists()
    assert Path(report.csv_path).exists()
    assert Path(report.json_path).exists()
    assert Path(report.zip_path).exists()


def test_official_investigation_reports_missing_terms_without_finding(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("hermes.connectors.tcesp.doe_tcesp_pdf.DoeTcespPdfConnector._extract_pdf_pages", lambda _self, _content: [PAGE_46, PAGE_47])

    report = run_official_gazette_investigation(
        "https://doe.tce.sp.gov.br/",
        "Procure o processo TC-999999.989.26-0",
        "2026-07-09",
        "2026-07-09",
        limit=5,
        fetcher=fake_fetcher_that_rejects_homepage,
        deepseek_service=DeepSeekService(api_key=None),
        report_dir=tmp_path / "reports",
        raw_dir=tmp_path / "raw",
    )

    assert report.findings == []
    assert "Processos/termos não localizados" in report.markdown
    assert "TC-999999.989.26-0" in report.markdown
    assert "nao_encontrado" in report.markdown
    assert "https://doe.tce.sp.gov.br/" not in report.evidence_links


def fake_doe_tcesp_fetcher(fetched_urls: list[str]):
    def fetcher(url: str):
        fetched_urls.append(url)
        if url == "https://doe.tce.sp.gov.br/pdf/2026/07/doe-tce-2026-07-09.pdf":
            return {
                "url": url,
                "status_code": 200,
                "content_type": "application/pdf",
                "content": b"%PDF fake fixture",
                "text": "",
                "error": None,
            }
        return {
            "url": url,
            "status_code": 404,
            "content_type": "text/html",
            "content": b"",
            "text": "",
            "error": None,
        }

    return fetcher


def fake_fetcher_that_rejects_homepage(url: str):
    if url == "https://doe.tce.sp.gov.br/":
        raise AssertionError("DOE-TCESP homepage should not be fetched for processo/acordao mission")
    return fake_doe_tcesp_fetcher([])(url)
