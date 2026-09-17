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


class UpdateCredentialsRequest(BaseModel):
    okx_env: Optional[str] = None
    okx_api_key: Optional[str] = None
    okx_secret_key: Optional[str] = None
    okx_passphrase: Optional[str] = None
    binance_env: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None


@router.post("/credentials", dependencies=[Depends(verify_admin_session)])
async def update_credentials(req: UpdateCredentialsRequest):
    """Update OKX, Binance, and LLM credentials dynamically."""
    if req.okx_env:
        settings.OKX_ENV = req.okx_env.lower()
    if req.okx_api_key is not None:
        if settings.OKX_ENV == "demo":
            settings.OKX_DEMO_API_KEY = req.okx_api_key
        else:
            settings.OKX_LIVE_API_KEY = req.okx_api_key
    if req.okx_secret_key is not None:
        if settings.OKX_ENV == "demo":
            settings.OKX_DEMO_SECRET_KEY = req.okx_secret_key
        else:
            settings.OKX_LIVE_SECRET_KEY = req.okx_secret_key
    if req.okx_passphrase is not None:
        if settings.OKX_ENV == "demo":
            settings.OKX_DEMO_PASSPHRASE = req.okx_passphrase
        else:
            settings.OKX_LIVE_PASSPHRASE = req.okx_passphrase

    if req.binance_env:
        settings.BINANCE_ENV = req.binance_env.lower()
    if req.binance_api_key is not None:
        if settings.BINANCE_ENV == "demo":
            settings.BINANCE_DEMO_API_KEY = req.binance_api_key
        else:
            settings.BINANCE_LIVE_API_KEY = req.binance_api_key
    if req.binance_secret_key is not None:
        if settings.BINANCE_ENV == "demo":
            settings.BINANCE_DEMO_SECRET_KEY = req.binance_secret_key
        else:
            settings.BINANCE_LIVE_SECRET_KEY = req.binance_secret_key

    if req.llm_api_key is not None:
        settings.LLM_API_KEY = req.llm_api_key
    if req.llm_base_url is not None:
        settings.LLM_BASE_URL = req.llm_base_url
    if req.llm_model is not None:
        settings.LLM_MODEL = req.llm_model

    return {"status": "success", "message": "API 凭证已动态更新生效"}


def mask_secret(s: str) -> str:
    if not s:
        return ""
    if len(s) < 8:
        return "******"
    return s[:3] + "..." + s[-3:]


@router.get("/credentials", dependencies=[Depends(verify_admin_session)])
async def get_credentials():
    """Retrieve masked credentials overview for admin console."""
    return {
        "okx_env": settings.OKX_ENV,
        "okx_api_key_masked": mask_secret(settings.OKX_LIVE_API_KEY if settings.OKX_ENV == "live" else settings.OKX_DEMO_API_KEY),
        "binance_env": settings.BINANCE_ENV,
        "binance_api_key_masked": mask_secret(settings.BINANCE_LIVE_API_KEY if settings.BINANCE_ENV == "live" else settings.BINANCE_DEMO_API_KEY),
        "llm_base_url": settings.LLM_BASE_URL,
        "llm_model": settings.LLM_MODEL,
        "llm_key_masked": mask_secret(settings.LLM_API_KEY)
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
