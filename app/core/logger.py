"""
Core logging module for KDP Translator.

Provides:
- Standard logging setup with file and console handlers.
- LogViewHandler: stores log records in a deque (maxlen=1000) for GUI display.
- get_logger(): convenience function returning the module-level logger.
"""

import logging
import sys
from collections import deque
from pathlib import Path
from typing import Deque, Optional

_LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
_DEFAULT_LOG_DIR: Path = Path("logs")
_DEFAULT_LOG_FILE: str = "kdptranslator.log"


class LogViewHandler(logging.Handler):
    """A logging handler that keeps the last *maxlen* records in a deque
    so that a GUI widget can display them without hitting the filesystem."""

    def __init__(self, level: int = logging.NOTSET, maxlen: int = 1000) -> None:
        super().__init__(level=level)
        self.records: Deque[logging.LogRecord] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        """Append the record (already formatted) to the deque."""
        self.records.append(record)

    def get_formatted_records(self) -> list[str]:
        """Return the most recent records as a list of formatted strings."""
        fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        return [fmt.format(r) for r in self.records]

    def clear(self) -> None:
        """Remove all stored records."""
        self.records.clear()


# ---------------------------------------------------------------------------
# Module-level logger setup
# ---------------------------------------------------------------------------

_logger: Optional[logging.Logger] = None
_view_handler: Optional[LogViewHandler] = None


def setup_logging(
    log_dir: Optional[Path] = None,
    log_file: Optional[str] = None,
    level: int = logging.DEBUG,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    max_view_records: int = 1000,
) -> logging.Logger:
    """Configure logging with file + console handlers and a LogViewHandler.

    Parameters
    ----------
    log_dir:
        Directory for the log file.  Defaults to ``logs/`` under the CWD.
    log_file:
        Name of the log file.  Defaults to ``kdptranslator.log``.
    level:
        Root logger level.
    console_level:
        Log level for the console (stderr) handler.
    file_level:
        Log level for the rotating file handler.
    max_view_records:
        Maximum number of records kept by the GUI view handler.

    Returns
    -------
    The configured root logger.
    """
    global _logger, _view_handler

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any pre-existing handlers from previous calls (idempotency).
    root_logger.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- Console handler (stderr) --------------------------------------------
    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # --- File handler ---------------------------------------------------------
    log_dir = log_dir or _DEFAULT_LOG_DIR
    log_file = log_file or _DEFAULT_LOG_FILE
    log_path = log_dir / log_file
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # --- GUI view handler -----------------------------------------------------
    _view_handler = LogViewHandler(maxlen=max_view_records)
    _view_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(_view_handler)

    root_logger.info(
        "Logging initialised — file: %s, level: %s",
        log_path.resolve(),
        logging.getLevelName(level),
    )

    _logger = root_logger
    return root_logger


def get_logger() -> logging.Logger:
    """Return the module-level logger.

    If :func:`setup_logging` has not been called yet, a basic configuration
    is performed automatically (this ensures that ``get_logger`` is always
    safe to call from any module at import time).
    """
    global _logger

    if _logger is None:
        _logger = setup_logging()

    return _logger


def get_view_handler() -> Optional[LogViewHandler]:
    """Return the active LogViewHandler instance (if any)."""
    return _view_handler
