from fastapi.testclient import TestClient

from hermes.api.app import create_app


def test_version_endpoint_returns_service_metadata() -> None:
    client = TestClient(create_app())
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "HERMES"
    assert body["version"] == "0.1.0"


def test_openapi_available_without_docs_ui() -> None:
    client = TestClient(create_app())

    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404

