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


def test_missing_path(client: TestClient) -> None:
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found"}
    }
