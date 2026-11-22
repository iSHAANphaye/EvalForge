"""Unit tests for EvalForge logging utilities."""

import logging

from evalforge.core.logging import get_logger, setup_logging


def test_setup_logging_and_get_logger():
    """Verify setup_logging and get_logger functions."""
    setup_logging(log_level="DEBUG")
    logger = get_logger("test_subsystem")
    assert logger.name == "evalforge.test_subsystem"
    assert logger.isEnabledFor(logging.DEBUG)

    logger_direct = get_logger("evalforge.custom")
    assert logger_direct.name == "evalforge.custom"
