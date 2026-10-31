from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from inspect import isawaitable
from typing import Literal

from fastapi import FastAPI
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from meadowlark.errors import install_error_handlers
from meadowlark.ready import ReadinessCheck
from meadowlark.request import install_request_middleware
from meadowlark.routes import router

Hook = Callable[[], Awaitable[None] | None]


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


async def _run_hook(hook: Hook) -> None:
    result = hook()
    if isawaitable(result):
        await result


def create_app(
    settings: Settings | None = None,
    *,
    on_startup: Sequence[Hook] = (),
    on_shutdown: Sequence[Hook] = (),
) -> FastAPI:
    if settings is None:
        settings = Settings()
    startup_hooks = list(on_startup)
    shutdown_hooks = list(on_shutdown)

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        index = 0
        while index < len(startup_hooks):
            hook = startup_hooks[index]
            index += 1
            await _run_hook(hook)
        yield
        index = 0
        while index < len(shutdown_hooks):
            hook = shutdown_hooks[index]
            index += 1
            await _run_hook(hook)

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.state.settings = settings
    application.state.readiness_checks: list[ReadinessCheck] = []
    application.state.startup_hooks = startup_hooks
    application.state.shutdown_hooks = shutdown_hooks
    install_request_middleware(
        application, settings.log_level, settings.log_format
    )
    install_error_handlers(application)
    application.include_router(router)
    return application
