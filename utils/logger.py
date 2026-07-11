"""
Logging system for graph_editor.

Provides a centralized logging setup that writes to both file and console.
Log files are stored in ``graph_editor/logs/`` with automatic rotation.

Usage
-----
    from utils.logger import get_logger

    log = get_logger(__name__)
    log.info("Application started")
    log.warning("Grid data missing, using defaults")
    log.error("PTDF computation failed: %s", e)

Log Levels
----------
- DEBUG: Detailed diagnostic information
- INFO: Normal operation milestones
- WARNING: Unexpected but non-critical events
- ERROR: Errors that may affect functionality
- CRITICAL: Fatal errors causing application termination
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "graph_editor.log"
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB per file
_BACKUP_COUNT = 3  # keep 3 rotated files

# ── Formatter ──────────────────────────────────────────────────────
_FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_CONSOLE_FORMAT = "%(levelname)-8s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    *,
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    console: bool = True,
    rotate: bool = True,
) -> None:
    """Configure the root logger.

    Parameters
    ----------
    level : int
        Logging level (default: ``logging.INFO``).
    log_file : str or Path, optional
        Path to log file. Defaults to ``logs/graph_editor.log``.
    console : bool
        Whether to emit logs to stderr (default: ``True``).
    rotate : bool
        Whether to use ``RotatingFileHandler`` (default: ``True``).
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on re-init
    logger.handlers.clear()

    # ── File handler ───────────────────────────────────────────────
    target = Path(log_file) if log_file else _LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    if rotate:
        fh = RotatingFileHandler(
            str(target), maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    else:
        fh = logging.FileHandler(str(target), encoding="utf-8")

    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(fh)

    # ── Console handler (stderr) ───────────────────────────────────
    if console:
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
        logger.addHandler(ch)

    logger.info("Logging initialized → %s", target)


# ── Convenience ────────────────────────────────────────────────────
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given *name*.

    Ensures the root logger is configured at least once.
    Returns a child logger of the ``graph_editor`` hierarchy.

    Parameters
    ----------
    name : str
        Usually ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
    """
    if name in _loggers:
        return _loggers[name]

    # Auto-init on first call if not already configured
    root = logging.getLogger()
    if not root.handlers:
        # Check environment variable for debug mode
        debug = os.environ.get("GRAPH_EDITOR_DEBUG", "").lower() in ("1", "true", "yes")
        setup_logging(level=logging.DEBUG if debug else logging.INFO)

    log = logging.getLogger(f"graph_editor.{name}")
    _loggers[name] = log
    return log

