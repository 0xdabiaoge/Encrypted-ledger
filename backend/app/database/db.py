"""
Encrypted Ledger - High-Performance Async Database Layer
SQLite with Write-Ahead Logging (WAL) for maximum concurrency and non-blocking reads.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from app.core.config import settings

Base = declarative_base()

DB_PATH = settings.DATA_DIR / "encrypted_ledger.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db() -> None:
    """Initialize database and enable SQLite WAL mode."""
    settings.ensure_directories()
    async with engine.begin() as conn:
        # Enable WAL mode and synchronous=NORMAL for durability + speed
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        await conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
        await conn.exec_driver_sql("PRAGMA busy_timeout=5000;")
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for FastAPI route handlers."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
