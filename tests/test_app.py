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


def test_invalid_body_uses_error_document(client: TestClient) -> None:
    response = client.post(
        "/echo",
        json={},
        headers={"X-Request-ID": "bad-1"},
    )
    assert response.status_code == 422
    assert response.headers["x-request-id"] == "bad-1"
    assert response.json() == {
        "error": {
            "code": "unprocessable_entity",
            "message": "Unprocessable Entity",
            "request_id": "bad-1",
            "fields": [
                {
                    "loc": ["body", "name"],
                    "message": "Field required",
                    "type": "missing",
                }
            ],
        }
    }


def test_invalid_body_field_type(client: TestClient) -> None:
    response = client.post(
        "/echo",
        json={"name": 1},
        headers={"X-Request-ID": "bad-2"},
    )
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "unprocessable_entity"
    assert body["error"]["request_id"] == "bad-2"
    assert body["error"]["fields"] == [
        {
            "loc": ["body", "name"],
            "message": "Input should be a valid string",
            "type": "string_type",
        }
    ]


def test_echo_accepts_name(client: TestClient) -> None:
    response = client.post(
        "/echo",
        json={"name": "ada"},
        headers={"X-Request-ID": "echo-1"},
    )
    assert response.status_code == 200
    assert response.json() == {"name": "ada"}
    assert response.headers["x-request-id"] == "echo-1"


def test_unhandled_error_keeps_error_document() -> None:
    application = create_app(Settings())

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret")

    client = TestClient(application, raise_server_exceptions=False)
    response = client.get("/boom", headers={"X-Request-ID": "boom-1"})
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "Internal Server Error",
            "request_id": "boom-1",
        }
    }
    assert "secret" not in response.text


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEADOWLARK_APP_NAME", "copied-app")
    monkeypatch.setenv("MEADOWLARK_LOG_LEVEL", "warning")
    application = create_app()
    assert application.title == "copied-app"
    assert logging.getLogger("meadowlark").level == logging.WARNING
