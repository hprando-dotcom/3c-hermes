import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from hermes.api.app import create_app
from hermes.database.session import get_session
from hermes.services.official_gazette_investigation import GazetteFinding, InvestigationReport


def test_version_endpoint_returns_service_metadata() -> None:
    client = TestClient(create_app())
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "HERMES"
    assert body["version"] == "0.1.0"


def test_openapi_and_docs_available() -> None:
    client = TestClient(create_app())

    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 404


def test_home_page_returns_html() -> None:
    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "HERMES" in response.text
    assert "HERMES investiga Diários Oficiais para você." in response.text
    assert "Começar investigação" in response.text
    assert "Consulta avancada TCE-SP" in response.text or "TCE-SP" in response.text


def test_pmsp_summary_page_returns_html() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)
    response = client.get("/pmsp/resumo?ano=2015")

    assert response.status_code == 200
    assert "Resumo" in response.text or "consultar" in response.text


def test_pmsp_search_page_returns_html() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)
    response = client.get("/pmsp?ano=2015&termo=engenharia")

    assert response.status_code == 200
    assert "Consulta" in response.text or "consultar" in response.text


def test_mission_pages_return_html_for_initial_intents() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)

    for path in (
        "/missao?q=obras",
        "/missao?q=fornecedores",
        "/missao?q=sa%C3%BAde",
    ):
        response = client.get(path)

        assert response.status_code == 200
        assert "Resumo executivo" in response.text
        assert "Resultado da missao" in response.text


def test_reports_page_empty_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("hermes.api.routes.mission.EXPORTS_DIR", tmp_path)
    client = TestClient(create_app())
    response = client.get("/relatorios")

    assert response.status_code == 200
    assert "Nenhum dossiê gerado ainda" in response.text


def test_reports_page_lists_generated_dossier(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "investigation_id": "hermes_diario_20260710_153000",
        "generated_at": "2026-07-10T15:30:00",
        "mission_text": "obras",
        "source_url": "https://diario.exemplo.gov.br",
        "date_start": "2026-07-01",
        "date_end": "2026-07-10",
        "deepseek_used": True,
        "totals": {"findings": 2},
        "report_html_path": "data/reports/hermes_diario_20260710_153000.html",
        "report_markdown_path": "data/reports/hermes_diario_20260710_153000.md",
        "csv_path": "data/exports/hermes_diario_20260710_153000_achados.csv",
        "json_path": "data/exports/hermes_diario_20260710_153000.json",
        "zip_path": "data/exports/hermes_diario_20260710_153000_dossie.zip",
    }
    (tmp_path / "hermes_diario_20260710_153000.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("hermes.api.routes.mission.EXPORTS_DIR", tmp_path)
    client = TestClient(create_app())
    response = client.get("/relatorios")

    assert response.status_code == 200
    assert "hermes_diario_20260710_153000" in response.text
    assert "Abrir relatório HTML" in response.text
    assert "Baixar Dossiê ZIP" in response.text


def test_publication_investigation_routes_return_html() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)

    for path in (
        "/investigar",
        "/fontes",
        "/publicacoes",
        "/publicacoes/resumo",
    ):
        response = client.get(path)

        assert response.status_code == 200
        assert "HERMES" in response.text or "fonte" in response.text.lower() or "publica" in response.text.lower()


def test_investigar_get_with_query_params_uses_investigation_service(monkeypatch) -> None:
    monkeypatch.setattr("hermes.api.routes.publications_ui.run_official_gazette_investigation", fake_investigation)
    client = TestClient(create_app())

    response = client.get(
        "/investigar?source_url=https://diario.exemplo.gov.br&mission=obras&date_start=2026-07-01&date_end=2026-07-10&limit=5"
    )

    assert response.status_code == 200
    assert "Relatório HERMES" in response.text
    assert "Contrato obras" in response.text
    assert "Produto gerado pelo HERMES" in response.text
    assert "Baixar relatório Markdown" in response.text
    assert "Baixar Dossiê ZIP" in response.text


def test_investigar_post_uses_investigation_service(monkeypatch) -> None:
    monkeypatch.setattr("hermes.api.routes.publications_ui.run_official_gazette_investigation", fake_investigation)
    client = TestClient(create_app())

    response = client.post(
        "/investigar",
        data={
            "source_url": "https://diario.exemplo.gov.br",
            "mission": "obras",
            "date_start": "2026-07-01",
            "date_end": "2026-07-10",
            "limit": "5",
        },
    )

    assert response.status_code == 200
    assert "Relatório HERMES" in response.text
    assert "Produto gerado pelo HERMES" in response.text


def test_downloads_allowed_file(monkeypatch, tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    export_dir = tmp_path / "exports"
    report_dir.mkdir()
    export_dir.mkdir()
    filename = "hermes_diario_20260710_153000.md"
    (report_dir / filename).write_text("# Relatório", encoding="utf-8")
    monkeypatch.setattr("hermes.api.routes.publications_ui.REPORTS_DIR", report_dir)
    monkeypatch.setattr("hermes.api.routes.publications_ui.EXPORTS_DIR", export_dir)
    client = TestClient(create_app())

    response = client.get(f"/downloads/{filename}")

    assert response.status_code == 200
    assert "Relatório" in response.text


def test_downloads_block_path_traversal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("hermes.api.routes.publications_ui.REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr("hermes.api.routes.publications_ui.EXPORTS_DIR", tmp_path / "exports")
    client = TestClient(create_app())

    response = client.get("/downloads/..%2F.env")

    assert response.status_code == 404


def test_downloads_block_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("hermes.api.routes.publications_ui.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("hermes.api.routes.publications_ui.EXPORTS_DIR", tmp_path)
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get("/downloads/.env")

    assert response.status_code == 404


def test_tcesp_home_page_returns_html() -> None:
    client = TestClient(create_app())
    response = client.get("/tcesp")

    assert response.status_code == 200
    assert "TCE-SP" in response.text
    assert "Despesas" in response.text


def test_tcesp_summary_page_returns_html() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)
    response = client.get("/tcesp/resumo?ano=2015")

    assert response.status_code == 200
    assert "Resumo" in response.text or "consultar" in response.text


def test_tcesp_html_query_pages_return_html() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)

    for path in (
        "/tcesp/municipios",
        "/tcesp/despesas?municipio=balsamo&ano=2015&mes=1&termo=engenharia",
        "/tcesp/receitas?municipio=balsamo&ano=2015&mes=1&termo=tesouro",
    ):
        response = client.get(path)

        assert response.status_code == 200
        assert "HERMES" in response.text or "TCE-SP" in response.text or "consultar" in response.text


def test_tcesp_search_redirects_by_type() -> None:
    client = TestClient(create_app())

    response = client.get("/tcesp/buscar?tipo=receitas&municipio=balsamo&ano=2015&mes=1", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/tcesp/receitas?")


def test_tcesp_json_endpoints_return_controlled_response() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)

    for path in (
        "/api/tcesp/municipios",
        "/api/tcesp/despesas?municipio=balsamo&ano=2015&mes=1",
        "/api/tcesp/receitas?municipio=balsamo&ano=2015&mes=1",
        "/api/tcesp/resumo?ano=2015",
    ):
        response = client.get(path)

        assert response.status_code == 200
        assert response.json()["ok"] is False


def test_status_page_returns_html_without_database() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    client = TestClient(app)
    response = client.get("/status")

    assert response.status_code == 200
    assert "Status HERMES" in response.text


def fake_session():
    yield FailingSession()


class FailingSession:
    def scalar(self, _statement):
        raise SQLAlchemyError("database unavailable in test")

    def scalars(self, _statement):
        raise SQLAlchemyError("database unavailable in test")

    def execute(self, _statement):
        raise SQLAlchemyError("database unavailable in test")


def fake_investigation(source_url, mission_text, date_start, date_end, limit=50, **_kwargs):
    finding = GazetteFinding(
        title="Contrato obras",
        date="2026-07-10",
        event_type="contrato",
        natureza="obras_engenharia",
        score=92,
        agency="Secretaria de Obras",
        company_name="CONSTRUTORA EXEMPLO",
        process_number="123/2026",
        contract_number="88/2026",
        value_text="R$ 10,00",
        object_text="Obras",
        summary="Contrato de obras",
        reason="termos encontrados",
        matched_terms=["obras"],
        snippet="Contrato de obras",
        link="https://diario.exemplo.gov.br/ato",
    )
    return InvestigationReport(
        investigation_id="hermes_diario_20260710_153000",
        source_url=source_url,
        mission_text=mission_text,
        date_start=date_start,
        date_end=date_end,
        strategy="mock",
        mission_context={"all_terms": ["obras"]},
        links_found=1,
        documents_analyzed=1,
        findings=[finding],
        limitations=[],
        evidence_links=[finding.link],
        markdown="# Relatório HERMES\n\nContrato obras",
        markdown_path="data/reports/mock.md",
        report_markdown_path="data/reports/hermes_diario_20260710_153000.md",
        report_html_path="data/reports/hermes_diario_20260710_153000.html",
        csv_path="data/exports/hermes_diario_20260710_153000_achados.csv",
        json_path="data/exports/hermes_diario_20260710_153000.json",
        zip_path="data/exports/hermes_diario_20260710_153000_dossie.zip",
        used_deepseek=False,
        metrics={"documents_analyzed": 1, "chunks_sent_to_ai": 0, "deepseek_calls": 0, "deepseek_failures": 0},
        totals={"links_found": 1, "documents_analyzed": 1, "findings": 1, "limitations": 0},
        generated_at="2026-07-10T15:30:00",
        report_html="<h1>Relatório HERMES</h1>",
    )
