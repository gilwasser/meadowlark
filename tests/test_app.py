import logging

import pytest
from fastapi.testclient import TestClient

from meadowlark import Settings, create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings()))


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_id_on_success(client: TestClient) -> None:
    response = client.get("/", headers={"X-Request-ID": "success-1"})
    assert response.status_code == 200
    assert response.json() == {"message": "hello"}
    assert response.headers["x-request-id"] == "success-1"


def test_request_id_on_not_found(client: TestClient) -> None:
    response = client.get("/missing", headers={"X-Request-ID": "missing-1"})
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "missing-1"
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": "missing-1",
        }
    }


def test_generated_request_id(client: TestClient) -> None:
    first = client.get("/health")
    second = client.get("/missing")
    first_id = first.headers["x-request-id"]
    second_id = second.headers["x-request-id"]
    assert first.status_code == 200
    assert second.status_code == 404
    assert first_id
    assert second_id
    assert first_id != second_id
    assert second.json()["error"]["request_id"] == second_id


def test_request_log(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="meadowlark")
    response = client.get("/health", headers={"X-Request-ID": "log-1"})
    assert response.status_code == 200
    assert "method=GET path=/health status=200 request_id=log-1" in caplog.messages


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEADOWLARK_APP_NAME", "copied-app")
    monkeypatch.setenv("MEADOWLARK_LOG_LEVEL", "warning")
    application = create_app()
    assert application.title == "copied-app"
    assert logging.getLogger("meadowlark").level == logging.WARNING
