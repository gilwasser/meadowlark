FROM python:3.12-slim AS build

WORKDIR /build
COPY pyproject.toml ./
COPY meadowlark ./meadowlark
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=build /install /usr/local
WORKDIR /app
RUN useradd --create-home --uid 1000 meadowlark \
    && chown meadowlark:meadowlark /app
USER meadowlark
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"]
CMD ["uvicorn", "meadowlark:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
