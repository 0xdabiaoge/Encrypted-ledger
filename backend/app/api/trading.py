"""
Encrypted Ledger - Trading & Execution API
Positions, aggregated balance, manual close, and manual execution cycle trigger.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.api.auth import verify_admin_session
from app.exchanges.router import order_router
from app.scheduler.tasks import orchestrator

router = APIRouter(prefix="/trading", tags=["Trading Operations"])


class ClosePositionRequest(BaseModel):
    venue: str
    symbol: str
    side: str
    size: Optional[float] = None


@router.get("/positions", dependencies=[Depends(verify_admin_session)])
async def get_all_positions():
    """Retrieve all open positions across OKX and Binance."""
    positions = []
    errors = {}
    try:
        okx_pos = await order_router.okx.get_positions()
        positions.extend([p.__dict__ for p in okx_pos])
    except Exception as e:
        errors["okx"] = str(e)

    try:
        bin_pos = await order_router.binance.get_positions()
        positions.extend([p.__dict__ for p in bin_pos])
    except Exception as e:
        errors["binance"] = str(e)

    return {"positions": positions, "errors": errors}


@router.get("/balance", dependencies=[Depends(verify_admin_session)])
async def get_aggregated_balance():
    """Retrieve equity and margins across OKX and Binance."""
    bal_okx = None
    bal_bin = None
    errors = {}

    try:
        bal_okx = await order_router.okx.get_account_balance()
    except Exception as e:
        errors["okx"] = str(e)

    try:
        bal_bin = await order_router.binance.get_account_balance()
    except Exception as e:
        errors["binance"] = str(e)

    total_equity = (bal_okx.total_equity_usd if bal_okx else 0.0) + (bal_bin.total_equity_usd if bal_bin else 0.0)
    total_avail = (bal_okx.available_usd if bal_okx else 0.0) + (bal_bin.available_usd if bal_bin else 0.0)
    total_margin = (bal_okx.margin_used_usd if bal_okx else 0.0) + (bal_bin.margin_used_usd if bal_bin else 0.0)
    total_upl = (bal_okx.unrealized_pnl_usd if bal_okx else 0.0) + (bal_bin.unrealized_pnl_usd if bal_bin else 0.0)

    return {
        "total_equity_usd": round(total_equity, 2),
        "available_usd": round(total_avail, 2),
        "margin_used_usd": round(total_margin, 2),
        "unrealized_pnl_usd": round(total_upl, 2),
        "okx": bal_okx.__dict__ if bal_okx else None,
        "binance": bal_bin.__dict__ if bal_bin else None,
        "errors": errors
    }


@router.post("/cycle/trigger", dependencies=[Depends(verify_admin_session)])
async def trigger_cycle():
    """Manually trigger an immediate trade scan and execution cycle."""
    try:
        res = await orchestrator.execute_trade_cycle()
        return {"status": "success", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/close", dependencies=[Depends(verify_admin_session)])
async def close_position(req: ClosePositionRequest):
    """Manually close a specific open position."""
    adapter = order_router.get_adapter(req.venue)
    try:
        res = await adapter.close_position(req.symbol, req.side, req.size)
        return {"status": "success", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
