import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from meadowlark import Hook, Settings, create_app
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
    with TestClient(application) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_service_unavailable_when_a_check_fails() -> None:
    application = create_app(Settings())
    register_readiness_check(application, lambda: True)
    register_readiness_check(application, lambda: False)
    with TestClient(application) as client:
        response = client.get("/ready", headers={"X-Request-ID": "ready-2"})
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
    with TestClient(application) as client:
        health = client.get("/health")
        ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 503


def test_readiness_checks_stay_on_their_app() -> None:
    failing = create_app(Settings())
    passing = create_app(Settings())
    register_readiness_check(failing, lambda: False)
    with TestClient(failing) as failing_client:
        failing_response = failing_client.get("/ready")
    with TestClient(passing) as passing_client:
        passing_response = passing_client.get("/ready")
    assert failing_response.status_code == 503
    assert passing_response.status_code == 200
    assert passing_response.json() == {"status": "ready"}


def test_readiness_check_is_recorded_when_startup_runs() -> None:
    seen: list[int] = []

    def observe() -> None:
        seen.append(len(application.state.readiness_checks))

    application = create_app(Settings(), on_startup=(observe,))
    register_readiness_check(application, lambda: False)
    before = TestClient(application).get("/ready")
    with TestClient(application) as client:
        during = client.get("/ready")
    assert before.status_code == 200
    assert before.json() == {"status": "ready"}
    assert seen == [0]
    assert during.status_code == 503


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


def _pin_perf_counter(monkeypatch: pytest.MonkeyPatch, start: float, end: float) -> None:
    samples = iter((start, end))
    monkeypatch.setattr("meadowlark.request._perf_counter", lambda: next(samples))


def test_request_log(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_perf_counter(monkeypatch, 2.0, 2.25)
    caplog.set_level(logging.INFO, logger="meadowlark")
    response = client.get("/health", headers={"X-Request-ID": "log-1"})
    assert response.status_code == 200
    assert (
        "method=GET path=/health status=200 request_id=log-1 duration_ms=250.0"
        in caplog.messages
    )


def test_request_log_text(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_perf_counter(monkeypatch, 2.0, 2.25)
    application = create_app(Settings(log_format="text"))
    caplog.set_level(logging.INFO, logger="meadowlark")
    response = TestClient(application).get(
        "/health", headers={"X-Request-ID": "text-1"}
    )
    assert response.status_code == 200
    assert (
        "method=GET path=/health status=200 request_id=text-1 duration_ms=250.0"
        in caplog.messages
    )


def test_request_log_json(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_perf_counter(monkeypatch, 2.0, 2.25)
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
        "duration_ms": 250.0,
    }
    assert list(payload) == ["method", "path", "status", "request_id", "duration_ms"]


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


def test_invalid_log_level_names_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEADOWLARK_LOG_LEVEL", "nope")
    with pytest.raises(ValidationError) as raised:
        create_app()
    message = str(raised.value)
    assert "MEADOWLARK_LOG_LEVEL" in message
    assert "DEBUG" in message


def test_invalid_log_format_names_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEADOWLARK_LOG_FORMAT", "xml")
    with pytest.raises(ValidationError) as raised:
        create_app()
    message = str(raised.value)
    assert "MEADOWLARK_LOG_FORMAT" in message
    assert "json" in message


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = create_app(Settings())

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret")

    _pin_perf_counter(monkeypatch, 2.0, 2.25)
    caplog.set_level(logging.INFO, logger="meadowlark")
    client = TestClient(application, raise_server_exceptions=False)
    response = client.get("/boom", headers={"X-Request-ID": "boom-1"})
    assert response.status_code == 500
    body = response.json()
    assert body == {
        "error": {
            "code": "internal_server_error",
            "message": "Internal Server Error",
            "request_id": "boom-1",
        }
    }
    assert response.headers["x-request-id"] == body["error"]["request_id"]
    assert "secret" not in response.text
    access = [message for message in caplog.messages if message.startswith("method=")]
    assert access == [
        "method=GET path=/boom status=500 request_id=boom-1 duration_ms=250.0"
    ]


def test_unhandled_error_log_json(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(Settings(log_format="json"))

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret")

    _pin_perf_counter(monkeypatch, 2.0, 2.25)
    caplog.set_level(logging.INFO, logger="meadowlark")
    client = TestClient(application, raise_server_exceptions=False)
    response = client.get("/boom", headers={"X-Request-ID": "boom-json-1"})
    assert response.status_code == 500
    assert response.headers["x-request-id"] == "boom-json-1"
    assert response.json()["error"]["request_id"] == "boom-json-1"
    line = next(message for message in caplog.messages if "boom-json-1" in message)
    assert json.loads(line) == {
        "method": "GET",
        "path": "/boom",
        "status": 500,
        "request_id": "boom-json-1",
        "duration_ms": 250.0,
    }


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


def test_startup_and_shutdown_hooks_run_in_order() -> None:
    events: list[str] = []

    def start_sync() -> None:
        events.append("start-sync")

    async def start_async() -> None:
        events.append("start-async")

    def stop_sync() -> None:
        events.append("stop-sync")

    async def stop_async() -> None:
        events.append("stop-async")

    application = create_app(
        Settings(),
        on_startup=(start_sync, start_async),
        on_shutdown=(stop_sync, stop_async),
    )
    with TestClient(application) as client:
        assert events == ["start-sync", "start-async"]
        response = client.get("/health")
        assert response.status_code == 200
    assert events == ["start-sync", "start-async", "stop-sync", "stop-async"]


def test_hooks_stay_on_the_app_that_registered_them() -> None:
    events: list[str] = []

    def start() -> None:
        events.append("start")

    def stop() -> None:
        events.append("stop")

    registered = create_app(
        Settings(),
        on_startup=(start,),
        on_shutdown=(stop,),
    )
    with TestClient(registered):
        with TestClient(create_app(Settings())):
            assert events == ["start"]
        assert events == ["start"]
    assert events == ["start", "stop"]


def test_create_app_keeps_the_hook_order_it_copied() -> None:
    events: list[str] = []
    startup: list[Hook] = []

    def first() -> None:
        events.append("first")

    def second() -> None:
        events.append("second")

    startup.extend((first, second))
    application = create_app(Settings(), on_startup=startup)
    startup.clear()
    startup.append(second)
    with TestClient(application):
        assert events == ["first", "second"]
