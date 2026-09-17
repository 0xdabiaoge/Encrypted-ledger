"""
Encrypted Ledger - Main FastAPI Application
Institutional Async Control Plane, Smart Order Router, and Automated Quant Engine.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.core.security import hash_password
from app.database.db import init_db, async_session_factory
from app.database.models import AdminUser
from app.api import api_v1_router
from app.scheduler.tasks import orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Sequence
    logger.info("Initializing Encrypted Ledger persistence layer...")
    await init_db()
    from app.core.credentials_store import load_persisted_credentials
    load_persisted_credentials()

    # Create default admin user if none exists
    async with async_session_factory() as session:
        res = await session.execute(select(AdminUser))
        admin = res.scalars().first()
        if not admin:
            default_pw = "Admin123!@#"
            pw_hash = hash_password(default_pw)
            initial_admin = AdminUser(username="admin", password_hash=pw_hash, role="superadmin")
            session.add(initial_admin)
            await session.commit()
            logger.warning("====================================================================")
            logger.warning("🔑 [INITIAL ADMIN CREATED] Username: admin | Password: Admin123!@#")
            logger.warning("   Please change this password immediately in the admin control panel!")
            logger.warning("====================================================================")

    # Start Trading & Sentinel Orchestrator
    orchestrator.start()

    yield

    # Shutdown Sequence
    logger.info("Shutting down Encrypted Ledger background services...")
    orchestrator.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="机构级双核驱动自动化量化加密货币交易与透明双式记账系统",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Router
app.include_router(api_v1_router)

# Mount Frontend SPA if built
FRONTEND_DIST = settings.PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    async def index_root():
        return {
            "app": settings.APP_NAME,
            "status": "online",
            "docs": "/docs",
            "api": "/api/v1",
            "message": "Encrypted Ledger backend active. Build frontend to view trading workstation UI."
        }
