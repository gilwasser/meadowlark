from collections.abc import Callable, Sequence

from fastapi import FastAPI

ReadinessCheck = Callable[[], bool]


def register_readiness_check(application: FastAPI, check: ReadinessCheck) -> None:
    def install() -> None:
        application.state.readiness_checks.append(check)

    application.state.startup_hooks.append(install)


def checks_pass(checks: Sequence[ReadinessCheck]) -> bool:
    return all(check() for check in checks)
