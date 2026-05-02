"""Observability — structured JSON logging via structlog.

`configure()` wires structlog to JSON output on stdout with timestamping and
log-level binding. Called at CLI startup; importing modules use
`structlog.get_logger(__name__)` to obtain a logger.
"""

import logging
import sys

import structlog


def configure(level: str = "INFO") -> None:
    """Configure structlog for JSON output on stdout.

    Idempotent — safe to call multiple times.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
