from __future__ import annotations

from pathlib import Path

from hermes.services.deepseek_service import DeepSeekService
from hermes.services.official_gazette_investigation import (
    GazetteDocument,
    build_mission_context,
    deterministic_classify_chunk,
    deterministic_report_markdown,
    extract_mission_terms,
    run_official_gazette_investigation,
)


SOURCE_HTML = """
<html><head><title>Diario Oficial</title></head><body>
  <a href="/diario/2026-07-10/contrato-obras.html">Diario Oficial 10/07/2026 contrato de obras</a>
  <a href="/diario/2026-07-09/aditivo-engenharia.pdf">Aditivo engenharia 09/07/2026 PDF</a>
</body></html>
"""

PUBLICATION_HTML = """
<html><body>
  <h1>Extrato de contrato</h1>
  <p>Órgão: Secretaria Municipal de Obras.</p>
  <p>Processo nº 12345/2026. Contrato nº 88/2026.</p>
  <p>Empresa: CONSTRUTORA EXEMPLO LTDA.</p>
  <p>Objeto: execução de obras de drenagem e pavimentação na avenida central.</p>
  <p>Valor R$ 1.234.567,89.</p>
</body></html>
"""


def test_extract_mission_terms() -> None:
    terms = extract_mission_terms("obras contratos aditivos engenharia")

    assert "obras" in terms
    assert "contratos" in terms
    assert "engenharia" in terms


def test_deterministic_classification_contract_engineering() -> None:
    document = GazetteDocument(
        url="https://diario.exemplo.gov.br/contrato.html",
        title="Contrato obras",
        content_type="text/html",
        is_pdf=False,
        date="2026-07-10",
        text=PUBLICATION_HTML,
    )
    chunk = {"document": document, "snippet": PUBLICATION_HTML, "matched_terms": ["contrato", "obras", "engenharia"]}

    finding = deterministic_classify_chunk(chunk, ["contrato", "obras", "engenharia"])

    assert finding.event_type == "contrato"
    assert finding.natureza == "obras_engenharia"
    assert finding.process_number == "12345/2026."
    assert finding.contract_number == "88/2026."
    assert finding.value_text == "R$ 1.234.567,89."
    assert finding.score > 50


def test_run_official_gazette_investigation_with_fake_html_and_pdf(tmp_path: Path) -> None:
    report = run_official_gazette_investigation(
        "https://diario.exemplo.gov.br",
        "obras contratos aditivos engenharia",
        "2026-07-01",
        "2026-07-10",
        limit=5,
        fetcher=fake_fetcher,
        deepseek_service=DeepSeekService(api_key=None),
        report_dir=tmp_path,
    )

    assert report.links_found == 2
    assert report.documents_analyzed == 2
    assert report.findings
    assert report.findings[0].event_type in {"contrato", "aditivo"}
    assert report.used_deepseek is False
    assert Path(report.markdown_path).exists()
    assert "Relatório HERMES" in report.markdown
    assert any("PDF" in limitation or "pypdf" in limitation for limitation in report.limitations)


def test_markdown_report_does_not_invent_outside_mocked_evidence(tmp_path: Path) -> None:
    report = run_official_gazette_investigation(
        "https://diario.exemplo.gov.br",
        "obras contratos aditivos engenharia",
        "2026-07-01",
        "2026-07-10",
        limit=5,
        fetcher=fake_fetcher,
        deepseek_service=DeepSeekService(api_key=None),
        report_dir=tmp_path,
    )

    assert "CONSTRUTORA EXEMPLO" in report.markdown
    assert "Empresa Fantasma" not in report.markdown


def test_deterministic_report_markdown_sections() -> None:
    markdown = deterministic_report_markdown(
        {
            "mission_text": "obras",
            "source_url": "https://diario.exemplo.gov.br",
            "date_start": "2026-07-01",
            "date_end": "2026-07-10",
            "strategy": "teste",
            "links_found": 1,
            "documents_analyzed": 1,
            "findings": [],
            "limitations": ["fonte sem data explícita"],
            "evidence_links": ["https://diario.exemplo.gov.br/ato"],
        }
    )

    assert "## 1. Missão" in markdown
    assert "## 10. Próximas ações" in markdown
    assert "fonte sem data explícita" in markdown


def test_deepseek_service_valid_json_response(monkeypatch) -> None:
    monkeypatch.setattr("hermes.services.deepseek_service.httpx.Client", FakeDeepSeekClient)

    service = DeepSeekService(api_key="test-key", base_url="https://deepseek.test")
    result = service.expand_mission_terms("obras")

    assert result.ok is True
    assert result.used_deepseek is True
    assert result.data["termos_principais"] == ["obras"]


def test_deepseek_service_missing_key_fallback() -> None:
    service = DeepSeekService(api_key=None)
    result = service.classify_publication_snippet("contrato de obras", build_mission_context("obras"))

    assert result.ok is False
    assert result.used_deepseek is False
    assert "DEEPSEEK_API_KEY" in result.error


def test_deepseek_service_error_is_structured(monkeypatch) -> None:
    monkeypatch.setattr("hermes.services.deepseek_service.httpx.Client", FailingDeepSeekClient)

    service = DeepSeekService(api_key="test-key", base_url="https://deepseek.test")
    result = service.build_investigation_report({"findings": []})

    assert result.ok is False
    assert result.used_deepseek is True
    assert "RuntimeError" in result.error
    assert service.failures == 1


def fake_fetcher(url: str):
    if url == "https://diario.exemplo.gov.br":
        return {
            "url": url,
            "status_code": 200,
            "content_type": "text/html",
            "text": SOURCE_HTML,
            "content": SOURCE_HTML.encode("utf-8"),
            "error": None,
        }
    if url.endswith("contrato-obras.html"):
        return {
            "url": url,
            "status_code": 200,
            "content_type": "text/html",
            "text": PUBLICATION_HTML,
            "content": PUBLICATION_HTML.encode("utf-8"),
            "error": None,
        }
    if url.endswith(".pdf"):
        return {
            "url": url,
            "status_code": 200,
            "content_type": "application/pdf",
            "text": "",
            "content": b"%PDF invalid",
            "error": None,
        }
    raise AssertionError(f"Unexpected URL {url}")


class FakeDeepSeekClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, *_args, **_kwargs):
        return FakeDeepSeekResponse()


class FakeDeepSeekResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"termos_principais":["obras"],"termos_expandidos":["engenharia"],"tipos_evento_interesse":["contrato"],"natureza_objeto_interesse":["obras_engenharia"],"periodo_identificado":null,"query_humana_resumida":"obras"}'
                    }
                }
            ]
        }


class FailingDeepSeekClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, *_args, **_kwargs):
        raise RuntimeError("network down")
