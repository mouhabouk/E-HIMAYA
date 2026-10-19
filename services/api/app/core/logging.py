"""Structured JSON logging. Personal data must never be logged: log ids, not names or phone numbers."""

import logging
import sys

import structlog
import structlog.tracebacks


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Never render local variables: they can hold tokens or personal data.
            structlog.processors.ExceptionRenderer(structlog.tracebacks.ExceptionDictTransformer(show_locals=False)),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level.upper()]),
        cache_logger_on_first_use=True,
    )
