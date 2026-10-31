# Meadowlark

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
uvicorn meadowlark:create_app --factory --port 8000
```

`GET /` returns `{"message":"hello"}`. `GET /health` returns `{"status":"ok"}`. A missing path returns status 404 and `{"error":{"code":"not_found","message":"Not Found","request_id":"<id>"}}`.

`POST /echo` reads a JSON object with a `name` string and returns that object. When the body fails validation, the status is 422 and the body is `{"error":{"code":"unprocessable_entity","message":"Unprocessable Entity","request_id":"<id>","fields":[...]}}`. Each item in `fields` has `loc`, `message`, and `type`.

Send `X-Request-ID` to choose the id. If you omit the header, or the value contains a character other than letters, digits, `.`, `_`, or `-`, the app generates an id. The same id comes back on the response header and on `error.request_id`.

Each request writes one log line on the `meadowlark` logger. The line names `method`, `path`, `status`, and `request_id`.

## Test

```bash
pytest
```

## Environment

`Settings` reads environment variables that start with `MEADOWLARK_`. Copy `.env.example` to `.env` to set them.

`MEADOWLARK_APP_NAME` sets the API title. The default is `meadowlark`. `MEADOWLARK_LOG_LEVEL` sets the level of the `meadowlark` logger. The default is `INFO`. Accepted levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
