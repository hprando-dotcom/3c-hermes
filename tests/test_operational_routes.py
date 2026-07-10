from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from hermes.api.app import create_app
from hermes.database.session import get_session


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
    assert "Investigar" in response.text
    assert "Agente de Inteligencia sobre Publicacoes Publicas" in response.text
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


def test_reports_page_returns_html() -> None:
    client = TestClient(create_app())
    response = client.get("/relatorios")

    assert response.status_code == 200
    assert "Relatorios" in response.text


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
