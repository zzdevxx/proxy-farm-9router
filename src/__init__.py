#!/usr/bin/env python3
"""proxy-farm-9router — kumpulkan proxy publik, uji, dan sunting ke DB 9router."""

__version__ = "2.0.0"

from .logger import get_logger, setup_logging

__all__ = ["__version__", "get_logger", "setup_logging"]
