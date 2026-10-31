from http import HTTPStatus
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEADOWLARK_", frozen=True)


class HelloResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def _error_response(status_code: int, message: str) -> JSONResponse:
    try:
        code = HTTPStatus(status_code).name.lower()
    except ValueError:
        code = "http_error"
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    application = FastAPI()
    application.state.settings = settings

    @application.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return _error_response(exc.status_code, message)

    @application.exception_handler(Exception)
    async def unhandled_error(_request: Request, _exc: Exception) -> JSONResponse:
        return _error_response(500, HTTPStatus.INTERNAL_SERVER_ERROR.phrase)

    @application.get("/")
    def read_root() -> HelloResponse:
        return HelloResponse(message="hello")

    @application.get("/health")
    def read_health() -> HealthResponse:
        return HealthResponse(status="ok")

    return application
