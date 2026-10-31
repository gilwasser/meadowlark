from collections.abc import Callable, Sequence

from fastapi import FastAPI

ReadinessCheck = Callable[[], bool]


def register_readiness_check(application: FastAPI, check: ReadinessCheck) -> None:
    application.state.readiness_checks.append(check)


def checks_pass(checks: Sequence[ReadinessCheck]) -> bool:
    return all(check() for check in checks)
