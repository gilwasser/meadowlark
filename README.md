# API

Install the dependencies, then start the server.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --port 8000
```

`GET /` returns `{"message":"hello"}`. `GET /health` returns `{"status":"ok"}`.
