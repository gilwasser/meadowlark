# Run and extend Meadowlark

Meadowlark is a small FastAPI app. Use this file to run it and to add to it in the shape the code already uses.

## Stack

The project needs Python 3.12 or newer. CI runs Python 3.12. Runtime dependencies are `fastapi`, `uvicorn`, and `pydantic-settings`. The `dev` extra adds `pytest` and `httpx`.

## Run

Install into a virtual environment, then start the app with the factory flag.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn meadowlark:create_app --factory --port 8000
```

The router in `meadowlark/routes.py` has two routes.

- `GET /` returns `{"message":"hello"}`.
- `GET /health` returns `{"status":"ok"}`.

A missing path returns status 404 and the error document below.

## Test

Run `pytest`. CI installs with `pip install -e ".[dev]"` and then runs `python -m pytest`. Tests live in `tests/test_app.py` and use `TestClient`.

## Lint

Ruff and mypy are coming. Neither is in `pyproject.toml` or in CI. Do not run them as commands that work today.

## Extend the app

`create_app` in `meadowlark/__init__.py` calls one `install_*` function per concern. The existing ones are `install_request_middleware` and `install_error_handlers`. If you add a concern, add another `install_*` function and call it from `create_app`.

`create_app` runs these steps in order.

1. Create `FastAPI` with `title` set to `settings.app_name`.
2. Set `application.state.settings`.
3. Call `install_request_middleware` with `settings.log_level`.
4. Call `install_error_handlers`.
5. Include `router`.

With no arguments, `create_app` builds `Settings` from the environment and from `.env`. Pass a `Settings` instance when the caller must set the values.

Routes return typed pydantic models. The route models are `HelloResponse` and `HealthResponse`. The error models are `ErrorResponse`, `ErrorDetail`, and `FieldError`.

## Settings

`Settings` is a frozen `BaseSettings` class. It reads variables with the prefix `MEADOWLARK_` and reads the `.env` file. It ignores extra keys. Copy `.env.example` to `.env` to set values.

- `app_name` defaults to `meadowlark`.
- `log_level` defaults to `INFO`. The allowed values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.

A string `log_level` is stripped and uppercased before the check. `warning` becomes `WARNING`.

Each app keeps its own log level. `install_request_middleware` builds a new `logging.Logger("meadowlark")` and sets that logger's level. The logger from `logging.getLogger("meadowlark")` stays as it was.

## Error shape

Every error uses one body.

```json
{"error": {"code": "not_found", "message": "Not Found", "request_id": "<id>"}}
```

`fields` is present only on validation errors. The code drops it when it is `None`, because `_error_response` calls `model_dump(exclude_none=True)`. Each item in `fields` has `loc`, `message`, and `type`.

`code` is the lowercased `HTTPStatus` name for that status. An unknown status uses `http_error`.

- 404 gives `not_found`.
- 422 gives `unprocessable_entity`.
- 500 gives `internal_server_error`.

The 500 body has the message `Internal Server Error`. It does not include the text of the exception.

## Request ID

The middleware reads the `X-Request-ID` header. It keeps the value only when the stripped value matches `^[A-Za-z0-9._-]{1,128}$`. Otherwise it uses `uuid.uuid4().hex`.

The middleware stores the id on `request.state.request_id`. Code that needs the id calls `request_id_for`.

When a request completes, the middleware sets the `X-Request-ID` response header. It also logs one line with `method`, `path`, `status`, and `request_id`.

An unhandled exception still returns `request_id` in the 500 body. That response has no `X-Request-ID` header. The middleware writes no log line for it.
