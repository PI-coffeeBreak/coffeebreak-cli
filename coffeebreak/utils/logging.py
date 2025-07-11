"""Logging configuration for CoffeeBreak CLI."""

import logging
import sys
from typing import Optional


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Setup logging configuration for the CLI.

    Args:
        verbose: Enable verbose/debug logging
        log_file: Optional log file path
    """
    # Set logging level
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)

    # Setup file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("docker").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("git").setLevel(logging.WARNING)
