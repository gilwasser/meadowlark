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

`GET /` returns `{"message":"hello"}`. `GET /health` returns `{"status":"ok"}`. A missing path returns status 404 and `{"error":{"code":"not_found","message":"Not Found"}}`.

## Test

```bash
pytest
```

## Environment

`Settings` reads environment variables that start with `MEADOWLARK_`. No variables are defined.
