from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HelloResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI()


@app.get("/")
def read_root() -> HelloResponse:
    return HelloResponse(message="hello")


@app.get("/health")
def read_health() -> HealthResponse:
    return HealthResponse(status="ok")
