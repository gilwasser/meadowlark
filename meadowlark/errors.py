from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from meadowlark.request import record_response, request_id_for


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


def install_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return _error_response(exc.status_code, message, request_id_for(request))

    @application.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY.value,
            HTTPStatus.UNPROCESSABLE_ENTITY.phrase,
            request_id_for(request),
            _field_errors(exc),
        )

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, _exc: Exception) -> JSONResponse:
        request_id = request_id_for(request)
        response = _error_response(
            500,
            HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            request_id,
        )
        record_response(request, response, request_id)
        return response
