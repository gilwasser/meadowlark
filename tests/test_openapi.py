import json
from pathlib import Path

import pytest

from meadowlark import Settings, create_app

SNAPSHOT = Path(__file__).with_name("openapi.json")


def _shipped_settings() -> Settings:
    kwargs = {
        name: field.get_default(call_default_factory=True)
        for name, field in Settings.model_fields.items()
        if not field.is_required()
    }
    return Settings(**kwargs)


def _canonical_json(document: object) -> str:
    return json.dumps(
        document,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def _live_text() -> str:
    return _canonical_json(create_app(_shipped_settings()).openapi())


def test_openapi_matches_snapshot() -> None:
    if not SNAPSHOT.is_file():
        raise AssertionError(
            "tests/openapi.json is missing. Regenerate it with python tests/test_openapi.py"
        )
    committed = SNAPSHOT.read_text(encoding="utf-8")
    assert committed == _live_text(), (
        "OpenAPI document differs from tests/openapi.json. "
        "Regenerate it with python tests/test_openapi.py"
    )


def test_openapi_ignores_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEADOWLARK_APP_NAME", "renamed")
    monkeypatch.setenv("MEADOWLARK_LOG_LEVEL", "ERROR")
    assert _live_text() == SNAPSHOT.read_text(encoding="utf-8")


def write_snapshot() -> None:
    SNAPSHOT.write_text(_live_text(), encoding="utf-8")


def main() -> None:
    write_snapshot()
    print("wrote tests/openapi.json")


if __name__ == "__main__":
    main()
