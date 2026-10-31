import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from meadowlark import Settings, create_app
from meadowlark.ready import register_readiness_check


class NameBody(BaseModel):
    name: str


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings()))


def _client_with_name_route() -> TestClient:
    application = create_app(Settings())

    @application.post("/checked")
    def checked(body: NameBody) -> NameBody:
        return body

    return TestClient(application)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_is_not_hello(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_ready_with_no_checks(client: TestClient) -> None:
    response = client.get("/ready", headers={"X-Request-ID": "ready-1"})
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["x-request-id"] == "ready-1"


def test_ready_when_checks_pass() -> None:
    application = create_app(Settings())
    register_readiness_check(application, lambda: True)
    response = TestClient(application).get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_service_unavailable_when_a_check_fails() -> None:
    application = create_app(Settings())
    register_readiness_check(application, lambda: True)
    register_readiness_check(application, lambda: False)
    response = TestClient(application).get(
        "/ready", headers={"X-Request-ID": "ready-2"}
    )
    assert response.status_code == 503
    assert response.headers["x-request-id"] == "ready-2"
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "Service Unavailable",
            "request_id": "ready-2",
        }
    }


def test_health_stays_ok_when_a_readiness_check_fails() -> None:
    application = create_app(Settings())
    register_readiness_check(application, lambda: False)
    client = TestClient(application)
    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 503


def test_readiness_checks_stay_on_their_app() -> None:
    failing = create_app(Settings())
    passing = create_app(Settings())
    register_readiness_check(failing, lambda: False)
    failing_response = TestClient(failing).get("/ready")
    passing_response = TestClient(passing).get("/ready")
    assert failing_response.status_code == 503
    assert passing_response.status_code == 200
    assert passing_response.json() == {"status": "ready"}


def test_request_id_on_success(client: TestClient) -> None:
    response = client.get("/v1", headers={"X-Request-ID": "success-1"})
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


def test_request_log_text(caplog: pytest.LogCaptureFixture) -> None:
    application = create_app(Settings(log_format="text"))
    caplog.set_level(logging.INFO, logger="meadowlark")
    response = TestClient(application).get(
        "/health", headers={"X-Request-ID": "text-1"}
    )
    assert response.status_code == 200
    assert (
        "method=GET path=/health status=200 request_id=text-1" in caplog.messages
    )


def test_request_log_json(caplog: pytest.LogCaptureFixture) -> None:
    application = create_app(Settings(log_format="json"))
    caplog.set_level(logging.INFO, logger="meadowlark")
    response = TestClient(application).get(
        "/health", headers={"X-Request-ID": "json-1"}
    )
    assert response.status_code == 200
    line = next(message for message in caplog.messages if "json-1" in message)
    payload = json.loads(line)
    assert payload == {
        "method": "GET",
        "path": "/health",
        "status": 200,
        "request_id": "json-1",
    }
    assert list(payload) == ["method", "path", "status", "request_id"]


def test_log_format_from_env(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MEADOWLARK_LOG_FORMAT", "JSON")
    application = create_app()
    assert application.state.settings.log_format == "json"
    caplog.set_level(logging.INFO, logger="meadowlark")
    response = TestClient(application).get(
        "/health", headers={"X-Request-ID": "env-json-1"}
    )
    assert response.status_code == 200
    line = next(message for message in caplog.messages if "env-json-1" in message)
    assert json.loads(line)["request_id"] == "env-json-1"


def test_invalid_body_uses_error_document() -> None:
    response = _client_with_name_route().post(
        "/checked",
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


def test_invalid_body_field_type() -> None:
    response = _client_with_name_route().post(
        "/checked",
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


def test_default_router_has_no_echo(client: TestClient) -> None:
    response = client.post(
        "/echo",
        json={"name": "ada"},
        headers={"X-Request-ID": "echo-1"},
    )
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "echo-1"
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["request_id"] == "echo-1"


def test_unhandled_error_keeps_error_document(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = create_app(Settings())

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret")

    caplog.set_level(logging.INFO, logger="meadowlark")
    client = TestClient(application, raise_server_exceptions=False)
    response = client.get("/boom", headers={"X-Request-ID": "boom-1"})
    assert response.status_code == 500
    assert response.headers.get("x-request-id") is None
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "Internal Server Error",
            "request_id": "boom-1",
        }
    }
    assert "secret" not in response.text
    assert "request_id=boom-1" not in " ".join(caplog.messages)


def test_settings_from_env(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MEADOWLARK_APP_NAME", "copied-app")
    monkeypatch.setenv("MEADOWLARK_LOG_LEVEL", "warning")
    shared = logging.getLogger("meadowlark")
    level_before = shared.level
    handlers_before = list(shared.handlers)
    application = create_app()
    assert application.title == "copied-app"
    assert shared.level == level_before
    assert list(shared.handlers) == handlers_before
    caplog.set_level(logging.INFO)
    response = TestClient(application).get("/health", headers={"X-Request-ID": "env-1"})
    assert response.status_code == 200
    assert "request_id=env-1" not in " ".join(caplog.messages)


def test_second_app_keeps_its_own_log_level(caplog: pytest.LogCaptureFixture) -> None:
    shared = logging.getLogger("meadowlark")
    level_before = shared.level
    handlers_before = list(shared.handlers)
    verbose = create_app(Settings(log_level="INFO"))
    quiet = create_app(Settings(log_level="ERROR"))
    assert shared.level == level_before
    assert list(shared.handlers) == handlers_before
    caplog.set_level(logging.INFO)
    verbose_response = TestClient(verbose).get(
        "/health", headers={"X-Request-ID": "keep-1"}
    )
    quiet_response = TestClient(quiet).get(
        "/health", headers={"X-Request-ID": "quiet-1"}
    )
    assert verbose_response.status_code == 200
    assert quiet_response.status_code == 200
    messages = " ".join(caplog.messages)
    assert "method=GET path=/health status=200 request_id=keep-1" in messages
    assert "request_id=quiet-1" not in messages
