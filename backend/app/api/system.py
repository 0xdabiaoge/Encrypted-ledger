"""
Encrypted Ledger - System Status & Dynamic Universe Management API
Health checks, exchange connectivity runtime indicators, and live instrument addition/removal.
"""
from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from app.api.auth import verify_admin_session
from app.core.config import settings
from app.quant.universe import universe_manager

router = APIRouter(prefix="/system", tags=["System Management"])


class AddInstrumentRequest(BaseModel):
    name: str
    ccy: Optional[str] = None
    tier: Optional[str] = "tier_2_momentum"
    max_leverage: Optional[float] = 3.0
    sl_atr_mult: Optional[float] = 2.2
    precision: Optional[int] = 2
    risk_per_trade_usd: Optional[float] = 15.0


@router.get("/health")
async def health_check():
    """System liveness and core subsystem integrity indicator."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }


@router.get("/runtime", dependencies=[Depends(verify_admin_session)])
async def get_runtime_status():
    """Reports dual-venue configured modes (demo vs live) and credentials readiness."""
    okx_ready = bool(
        (settings.OKX_ENV == "demo" and settings.OKX_DEMO_API_KEY) or
        (settings.OKX_ENV == "live" and settings.OKX_LIVE_API_KEY)
    )
    binance_ready = bool(
        (settings.BINANCE_ENV == "demo" and settings.BINANCE_DEMO_API_KEY) or
        (settings.BINANCE_ENV == "live" and settings.BINANCE_LIVE_API_KEY)
    )

    return {
        "okx": {
            "environment": settings.OKX_ENV,
            "status": "READY" if okx_ready else "DEMO_UNCONFIGURED",
            "is_demo": settings.OKX_ENV == "demo"
        },
        "binance": {
            "environment": settings.BINANCE_ENV,
            "status": "READY" if binance_ready else "DEMO_UNCONFIGURED",
            "is_demo": settings.BINANCE_ENV == "demo"
        },
        "routing": {
            "preferred_venue": settings.PREFERRED_VENUE,
            "mode": settings.ROUTING_MODE
        }
    }


@router.post("/universe/add", dependencies=[Depends(verify_admin_session)])
async def add_instrument_to_universe(req: AddInstrumentRequest):
    """Dynamically adds a custom cryptocurrency into the active trading universe."""
    try:
        universe_manager.add_instrument(req.model_dump())
        return {"status": "success", "message": f"标的 {req.name.upper()} 已成功添加至交易池"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/universe/{symbol}", dependencies=[Depends(verify_admin_session)])
async def remove_instrument_from_universe(symbol: str):
    """Dynamically removes a cryptocurrency from the trading universe."""
    success = universe_manager.remove_instrument(symbol)
    if not success:
        raise HTTPException(status_code=404, detail=f"标的 {symbol.upper()} 未在交易池中找到")
    return {"status": "success", "message": f"标的 {symbol.upper()} 已从交易池中移除"}


@router.put("/universe/{symbol}", dependencies=[Depends(verify_admin_session)])
async def update_instrument_in_universe(symbol: str, updates: Dict[str, Any]):
    """Update risk or precision settings for an existing instrument."""
    success = universe_manager.update_instrument(symbol, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"标的 {symbol.upper()} 未在交易池中找到")
    return {"status": "success", "message": f"标的 {symbol.upper()} 配置已更新"}
