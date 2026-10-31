import json
import logging
import re
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _resolve_request_id(header_value: str | None) -> str:
    if header_value is not None and _REQUEST_ID.fullmatch(header_value.strip()):
        return header_value.strip()
    return uuid.uuid4().hex


def request_id_for(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return _resolve_request_id(None)


def _request_logger(level: str) -> logging.Logger:
    request_logger = logging.Logger("meadowlark")
    request_logger.setLevel(level)
    request_logger.parent = logging.getLogger()
    request_logger.propagate = True
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    request_logger.addHandler(handler)
    return request_logger


def _request_log_line(
    method: str,
    path: str,
    status: int,
    request_id: str,
    log_format: str,
) -> str:
    fields = {
        "method": method,
        "path": path,
        "status": status,
        "request_id": request_id,
    }
    if log_format == "json":
        return json.dumps(fields)
    return "method=%s path=%s status=%s request_id=%s" % (
        method,
        path,
        status,
        request_id,
    )


def record_response(request: Request, response: Response, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    request.app.state.request_logger.info(
        _request_log_line(
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            request.app.state.log_format,
        )
    )


def install_request_middleware(
    application: FastAPI, log_level: str, log_format: str = "text"
) -> None:
    application.state.request_logger = _request_logger(log_level)
    application.state.log_format = log_format

    @application.middleware("http")
    async def add_request_id(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = _resolve_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        response = await call_next(request)
        record_response(request, response, request_id)
        return response
