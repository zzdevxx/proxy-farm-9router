"""Sistem logging terpusat untuk proxy-farm-9router.

Mendukung output ganda:
  1. File log berotasi (default: logs/farm.log, 5 MB, 5 cadangan):
     Format presisi ISO: [YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [module] Pesan
     Mencatat semua detail, debug, traceback galat tak tertangani.
  2. Terminal/Console:
     Format bersih, ramah progress bar (menghapus bar saat mencetak log baru).
     Warna ANSI untuk membedakan INFO, WARNING, ERROR, dan DEBUG.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from typing import Any

# ANSI color codes untuk terminal
_COLORS = {
    logging.DEBUG: "\033[2;37m",     # Dim white
    logging.INFO: "\033[0;36m",      # Cyan
    logging.WARNING: "\033[1;33m",   # Bright Yellow
    logging.ERROR: "\033[1;31m",     # Bright Red
    logging.CRITICAL: "\033[1;41m",  # Red background
}
_RESET = "\033[0m"


class CleanConsoleFormatter(logging.Formatter):
    """Formatter untuk terminal dengan pewarnaan level dan pesan ringkas."""

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        level_no = record.levelno
        msg = record.getMessage()

        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        if not self.use_color:
            if level_no >= logging.WARNING:
                return f"[{record.levelname}] {msg}"
            return msg

        color = _COLORS.get(level_no, "")
        if level_no == logging.INFO:
            return msg
        elif level_no >= logging.ERROR:
            return f"{color}[{record.levelname}] {msg}{_RESET}"
        elif level_no == logging.WARNING:
            return f"{color}[WARN] {msg}{_RESET}"
        elif level_no == logging.DEBUG:
            return f"{color}[DBG] {msg}{_RESET}"
        return f"{color}{msg}{_RESET}"


class ProgressAwareConsoleHandler(logging.StreamHandler):
    """Stream handler yang membersihkan sisa escape progress bar sebelum mencetak."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            # Jika baris sebelumnya adalah progress bar (\r), hapus baris dulu
            if sys.stdout.isatty():
                stream.write(f"\r\033[K{msg}\n")
            else:
                stream.write(f"{msg}\n")
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


_INITIALIZED = False
_ROOT_LOGGER_NAME = "farm"


def setup_logging(
    cfg: dict[str, Any] | None = None,
    level: str | None = None,
    log_file: str | None = None,
    repo_root: str | None = None,
) -> logging.Logger:
    """Inisialisasi sistem logging ganda (file + konsol) secara aman dan idempoten."""
    global _INITIALIZED

    root_dir = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_cfg = (cfg or {}).get("logging", {})

    enabled = log_cfg.get("enabled", True)
    log_dir_name = log_cfg.get("dir", "logs")
    log_file_name = log_file or log_cfg.get("file", "farm.log")
    max_bytes = int(log_cfg.get("max_bytes", 5 * 1024 * 1024))
    backup_count = int(log_cfg.get("backup_count", 5))

    # Tentukan level log (prioritas: CLI argument -> config.toml -> default INFO)
    effective_level_str = (level or log_cfg.get("level", "INFO")).upper()
    level_val = getattr(logging, effective_level_str, logging.INFO)

    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)  # Root farm menangkap semua, handler menyaring

    if _INITIALIZED:
        return logger

    logger.handlers.clear()

    # 1. Console Handler (Progress-Aware)
    ch = ProgressAwareConsoleHandler(sys.stdout)
    ch.setLevel(level_val)
    ch.setFormatter(CleanConsoleFormatter(use_color=sys.stdout.isatty()))
    logger.addHandler(ch)

    # 2. Rotating File Handler
    if enabled:
        logs_path = os.path.join(root_dir, log_dir_name)
        os.makedirs(logs_path, exist_ok=True)
        file_path = os.path.join(logs_path, log_file_name)

        fh = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        # File handler mencatat lebih detail (selalu minimal INFO, atau DEBUG jika disetel)
        fh.setLevel(logging.DEBUG if level_val == logging.DEBUG else logging.INFO)
        file_fmt = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d [%(levelname)-7s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(file_fmt)
        logger.addHandler(fh)

    # Kaitkan unhandled exception agar tercatat di file log sebelum proses mati
    def _uncaught_exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Pengecualian tak tertangani (Crash): %s: %s",
            exc_type.__name__,
            exc_value,
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _uncaught_exception_handler
    _INITIALIZED = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Dapatkan instance logger turunan di bawah hierarki 'farm'."""
    if not name or name == _ROOT_LOGGER_NAME:
        return logging.getLogger(_ROOT_LOGGER_NAME)
    if name.startswith(f"{_ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
