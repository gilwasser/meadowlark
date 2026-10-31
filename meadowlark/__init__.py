import logging
import re
import uuid
from http import HTTPStatus
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from meadowlark.routes import router

logger = logging.getLogger("meadowlark")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEADOWLARK_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )
    app_name: str = "meadowlark"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class FieldError(BaseModel):
    loc: list[str | int]
    message: str
    type: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    fields: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def _resolve_request_id(header_value: str | None) -> str:
    if header_value is not None and _REQUEST_ID.fullmatch(header_value.strip()):
        return header_value.strip()
    return uuid.uuid4().hex


def _error_response(
    status_code: int,
    message: str,
    request_id: str,
    fields: list[FieldError] | None = None,
) -> JSONResponse:
    try:
        code = HTTPStatus(status_code).name.lower()
    except ValueError:
        code = "http_error"
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=request_id,
            fields=fields,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
    )


def _field_errors(exc: RequestValidationError) -> list[FieldError]:
    parsed: list[FieldError] = []
    for err in exc.errors():
        loc: list[str | int] = []
        for part in err.get("loc", ()):
            if isinstance(part, (str, int)):
                loc.append(part)
            else:
                loc.append(str(part))
        parsed.append(
            FieldError(
                loc=loc,
                message=str(err.get("msg", "Invalid value")),
                type=str(err.get("type", "value_error")),
            )
        )
    return parsed


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return _resolve_request_id(None)


def _configure_logging(level: str) -> None:
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    application = FastAPI(title=settings.app_name)
    application.state.settings = settings
    _configure_logging(settings.log_level)

    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = _resolve_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "method=%s path=%s status=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
        )
        return response

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return _error_response(exc.status_code, message, _request_id(request))

    @application.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY.value,
            HTTPStatus.UNPROCESSABLE_ENTITY.phrase,
            _request_id(request),
            _field_errors(exc),
        )

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, _exc: Exception) -> JSONResponse:
        return _error_response(
            500,
            HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            _request_id(request),
        )

    application.include_router(router)
    return application
