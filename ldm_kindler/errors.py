"""Códigos de erro únicos e helpers de logging para diagnóstico."""
from __future__ import annotations

import logging
from typing import Any, Mapping

LOGGER_NAME = "kindlemake"


class ErrorCode:
    """Códigos estáveis (KM-ÁREA-NNN) para logs, API e suporte."""

    # API HTTP
    API_JOB_NOT_FOUND = "KM-API-001"
    API_FILE_NOT_FOUND = "KM-API-002"
    API_PATH_INVALID = "KM-API-003"
    API_LIBRARY_LIST_FAILED = "KM-API-004"
    API_VALIDATION_FAILED = "KM-API-005"
    API_INTERNAL = "KM-API-999"

    # Jobs em background
    JOB_NO_CHAPTERS = "KM-JOB-001"
    JOB_BUILD_FAILED = "KM-JOB-002"
    JOB_UNEXPECTED = "KM-JOB-003"
    JOB_COVER_FETCH_FAILED = "KM-JOB-004"
    JOB_CHAPTER_FAILED = "KM-JOB-005"

    # WebSocket
    WS_JOB_NOT_FOUND = "KM-WS-001"
    WS_CLIENT_ERROR = "KM-WS-002"

    # CLI (Typer)
    CLI_URL_TEMPLATE_REQUIRED = "KM-CLI-001"
    CLI_OUTPUT_FORMAT_INVALID = "KM-CLI-002"


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or LOGGER_NAME)


def api_error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    body.update(extra)
    return body


def log_error(
    logger: logging.Logger,
    code: str,
    message: str,
    *,
    extra: Mapping[str, Any] | None = None,
    exc_info: bool | BaseException = False,
) -> None:
    """Registra erro no stderr com código único; use exc_info=True dentro de except."""
    suffix = ""
    if extra:
        suffix = " | " + " ".join(f"{k}={v!r}" for k, v in extra.items())
    logger.error("[%s] %s%s", code, message, suffix, exc_info=exc_info)
