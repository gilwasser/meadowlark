from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from meadowlark.ready import checks_pass

router = APIRouter()


class HelloResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]


@router.get("/")
def read_root() -> HelloResponse:
    return HelloResponse(message="hello")


@router.get("/health")
def read_health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready")
def read_ready(request: Request) -> ReadyResponse:
    if checks_pass(request.app.state.readiness_checks):
        return ReadyResponse(status="ready")
    raise HTTPException(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
        detail=HTTPStatus.SERVICE_UNAVAILABLE.phrase,
    )
