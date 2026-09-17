"""
Encrypted Ledger - Structured Logging Engine
Unified async-safe logging with rotation and institutional formatting.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.config import settings


def setup_logger(name: str = "encrypted_ledger") -> logging.Logger:
    logger = logging.getLogger(name)
    level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    try:
        log_dir = settings.LOGS_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "encrypted_ledger.log",
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=10,
            encoding="utf-8"
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass

    return logger


logger = setup_logger()
