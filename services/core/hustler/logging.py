"""
K-007: Gözlemlenebilirlik (structlog)
- Geliştirme modunda renkli, üretimde JSON formatı.
- run_id taşıması (contextvars).
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# ContextVar for run_id
run_id_ctx: ContextVar[str] = ContextVar("run_id", default="")

def setup_logging(is_dev: bool = True) -> None:
    # Standart logging'i structlog'a yönlendir
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    def add_run_id(logger: logging.Logger, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        run_id = run_id_ctx.get()
        if run_id:
            event_dict["run_id"] = run_id
        return event_dict

    processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_run_id,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
