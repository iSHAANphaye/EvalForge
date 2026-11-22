"""Structured logging infrastructure using standard logging and RichHandler."""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(log_level: str = "INFO", console: Console | None = None) -> None:
    """Configure root and evalforge loggers with RichHandler for clear terminal diagnostics."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = RichHandler(
        console=console or Console(file=sys.stderr),
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=True,
    )
    handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    for h in list(root_logger.handlers):
        if isinstance(h, RichHandler):
            root_logger.removeHandler(h)

    root_logger.addHandler(handler)

    # Configure evalforge namespace
    evalforge_logger = logging.getLogger("evalforge")
    evalforge_logger.setLevel(level)


def get_logger(name: str = "evalforge") -> logging.Logger:
    """Obtain a logger instance within the evalforge namespace."""
    if not name.startswith("evalforge") and name != "":
        name = f"evalforge.{name}"
    return logging.getLogger(name)
