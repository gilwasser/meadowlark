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

`GET /v1` returns `{"message":"hello"}`. `GET /` is a missing path, not an alias of `/v1`. `GET /health` returns `{"status":"ok"}`. `GET /ready` returns `{"status":"ready"}` when every registered readiness check passes. Each app has its own readiness checks. A new app has none, so `GET /ready` returns ready. If a check fails, `GET /ready` returns status 503 and `{"error":{"code":"service_unavailable","message":"Service Unavailable","request_id":"<id>"}}`. A missing path returns status 404 and `{"error":{"code":"not_found","message":"Not Found","request_id":"<id>"}}`.

An invalid request body returns status 422 and `{"error":{"code":"unprocessable_entity","message":"Unprocessable Entity","request_id":"<id>","fields":[...]}}`. Each item in `fields` has `loc`, `message`, and `type`. The shipped routes do not include `POST /echo`.

Send `X-Request-ID` to choose the id. If you omit the header, or the value contains a character other than letters, digits, `.`, `_`, or `-`, the app generates an id. The same id comes back on the response header and on `error.request_id`.

Each finished request writes one log line. The line names `method`, `path`, `status`, and `request_id`. The default format is `text`, a single key=value line such as `method=GET path=/health status=200 request_id=<id>`. Set `MEADOWLARK_LOG_FORMAT` to `json` to write one JSON object with those four keys. `text` keeps the key=value line. `MEADOWLARK_LOG_LEVEL` sets that app's level. A second app in the same process keeps its own level.

`create_app` takes `on_startup` and `on_shutdown`. Each argument is a sequence of callbacks. A callback is a function or an async function. Startup callbacks run in the order you pass them when the app starts. Shutdown callbacks run in the order you pass them when the app stops. The app copies both sequences when you call `create_app`.

`register_readiness_check` adds a startup callback. That callback records the check when the app starts, after the callbacks in `on_startup`. `GET /ready` uses the recorded checks.

## Test

```bash
pytest
```

## Environment

`Settings` reads environment variables that start with `MEADOWLARK_`. Copy `.env.example` to `.env` to set them.

`MEADOWLARK_APP_NAME` sets the API title. The default is `meadowlark`. `MEADOWLARK_LOG_LEVEL` sets the request log level for that app. The default is `INFO`. Accepted levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. `MEADOWLARK_LOG_FORMAT` sets the request log line for that app. The default is `text`. Accepted values are `text` and `json`. Letter case does not matter.
