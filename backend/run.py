#!/usr/bin/env python3
"""
Encrypted Ledger - Main Application Entrypoint
Run this script to launch the FastAPI control plane, background scheduler, and market listeners.
"""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uvicorn
from app.core.config import settings
from app.core.logging import logger

if __name__ == "__main__":
    logger.info(f"Starting {settings.APP_NAME} on http://{settings.HOST}:{settings.PORT} ...")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower()
    )
