from typing import Literal

from fastapi import FastAPI
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from meadowlark.errors import install_error_handlers
from meadowlark.ready import ReadinessCheck
from meadowlark.request import install_request_middleware
from meadowlark.routes import router


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEADOWLARK_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )
    app_name: str = "meadowlark"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    application = FastAPI(title=settings.app_name)
    application.state.settings = settings
    application.state.readiness_checks: list[ReadinessCheck] = []
    install_request_middleware(
        application, settings.log_level, settings.log_format
    )
    install_error_handlers(application)
    application.include_router(router)
    return application
