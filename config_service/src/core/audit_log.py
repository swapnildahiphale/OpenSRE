from __future__ import annotations

import logging
import os
import sys
import uuid

import structlog


def configure_logging() -> None:
    """Enterprise-friendly structured logging.

    - JSON logs to stdout
    - adds timestamp, level, logger name
    - audit events emitted with `audit=True` field
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level, logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def new_request_id() -> str:
    return uuid.uuid4().hex


def audit_logger() -> structlog.stdlib.BoundLogger:
    return structlog.get_logger("audit")


def app_logger() -> structlog.stdlib.BoundLogger:
    return structlog.get_logger("app")
