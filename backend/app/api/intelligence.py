"""
Encrypted Ledger - Intelligence & Macro News API
Feeds 7x24 Jin10, Sina, and exchange operational announcements to dashboard and LLM context.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.api.auth import verify_admin_session
from app.intelligence.harvester import news_harvester

router = APIRouter(prefix="/intelligence", tags=["Macro Intelligence"])


@router.get("/news")
async def get_macro_news():
    """Retrieve latest cached macro intelligence news."""
    return news_harvester.get_latest_news_cache()


@router.post("/news/harvest", dependencies=[Depends(verify_admin_session)])
async def trigger_news_harvest():
    """Trigger an immediate live harvest across all global news feeds."""
    return await news_harvester.harvest_and_analyze()
