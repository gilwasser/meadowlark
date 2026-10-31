from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HelloResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"]


class EchoBody(BaseModel):
    name: str


@router.post("/echo")
def echo(body: EchoBody) -> EchoBody:
    return body


@router.get("/")
def read_root() -> HelloResponse:
    return HelloResponse(message="hello")


@router.get("/health")
def read_health() -> HealthResponse:
    return HealthResponse(status="ok")
