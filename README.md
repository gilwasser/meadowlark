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

An invalid request body returns status 422 and `{"error":{"code":"unprocessable_entity","message":"Unprocessable Entity","request_id":"<id>","fields":[...]}}`. Each item in `fields` has `loc`, `message`, and `type`. The shipped routes do not include `POST /echo`.

Send `X-Request-ID` to choose the id. If you omit the header, or the value contains a character other than letters, digits, `.`, `_`, or `-`, the app generates an id. The same id comes back on the response header and on `error.request_id`.

Each finished request writes one log line. The line names `method`, `path`, `status`, and `request_id`. `MEADOWLARK_LOG_LEVEL` sets that app's level. A second app in the same process keeps its own level.

## Test

```bash
pytest
```

## Environment

`Settings` reads environment variables that start with `MEADOWLARK_`. Copy `.env.example` to `.env` to set them.

`MEADOWLARK_APP_NAME` sets the API title. The default is `meadowlark`. `MEADOWLARK_LOG_LEVEL` sets the request log level for that app. The default is `INFO`. Accepted levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
