"""
Encrypted Ledger - Trading & Execution API
Supports role-based data masking:
- Guests / Regular Users: View commercial-grade track records with sensitive balance & size fields securely masked;
- Superadmin: Unlocks complete unmasked perspective with full operational control.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.api.auth import get_optional_session, verify_admin_session
from app.exchanges.router import order_router
from app.scheduler.tasks import orchestrator
from app.core.sharing import position_share_manager

router = APIRouter(prefix="/trading", tags=["Trading Operations"])


class ClosePositionRequest(BaseModel):
    venue: str
    symbol: str
    side: str
    size: Optional[float] = None


class CreatePositionShareRequest(BaseModel):
    symbol: str
    side: str
    leverage: str = "5.0x"
    entry_price: float = 0.0
    mark_price: float = 0.0
    unrealized_pnl_ratio: float = 0.0
    venue: str = "okx"
    council_insight: Optional[str] = ""
    custom_alias: Optional[str] = None


@router.get("/positions")
async def get_all_positions(session_payload=Depends(get_optional_session)):
    """
    Retrieve open positions across venues.
    Applies security data masking if requester is not authenticated as Superadmin.
    """
    is_admin = bool(session_payload and session_payload.get("role") in ("superadmin", "admin"))

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

    if is_admin:
        return {
            "positions": positions,
            "is_masked": False,
            "errors": errors
        }

    # Data Masking for Public / Guest / Regular Member display
    masked_positions = []
    for p in positions:
        ratio = float(p.get("unrealized_pnl_ratio", 0.0))
        masked_positions.append({
            "venue": p.get("venue"),
            "symbol": p.get("symbol"),
            "side": p.get("side"),
            "leverage": p.get("leverage"),
            "size": "***",  # Masked exact institutional lots
            "entry_price": round(float(p.get("entry_price", 0.0)), 2),
            "mark_price": round(float(p.get("mark_price", 0.0)), 2),
            "unrealized_pnl_usd": None,  # Masked dollar amount
            "unrealized_pnl_ratio": round(ratio, 4),  # Percentage return is transparent
            "status": "保本锁利中" if ratio >= 0.015 else ("盈利奔跑中" if ratio > 0 else "动态风控中"),
            "is_masked": True
        })

    return {
        "positions": masked_positions,
        "is_masked": True,
        "errors": errors
    }


@router.get("/balance")
async def get_aggregated_balance(session_payload=Depends(get_optional_session)):
    """
    Retrieve equity and account margins.
    Masked for public visitors to protect institutional treasury confidentiality.
    """
    is_admin = bool(session_payload and session_payload.get("role") in ("superadmin", "admin"))

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

    if is_admin:
        return {
            "total_equity_usd": round(total_equity, 2),
            "available_usd": round(total_avail, 2),
            "margin_used_usd": round(total_margin, 2),
            "unrealized_pnl_usd": round(total_upl, 2),
            "is_masked": False,
            "okx": bal_okx.__dict__ if bal_okx else None,
            "binance": bal_bin.__dict__ if bal_bin else None,
            "errors": errors
        }

    # Public Masked View
    return {
        "total_equity_usd": 0.0,
        "display_scale": "★ 100,000+ USDT",
        "is_masked": True,
        "okx": {"total_equity_usd": 0.0, "status": "接入正常 (OKX V5)"},
        "binance": {"total_equity_usd": 0.0, "status": "接入正常 (币安合约)"},
        "errors": errors
    }


@router.post("/cycle/trigger", dependencies=[Depends(verify_admin_session)])
async def trigger_cycle():
    """Manually trigger an immediate trade scan and execution cycle (Superadmin only)."""
    try:
        res = await orchestrator.execute_trade_cycle()
        return {"status": "success", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/close", dependencies=[Depends(verify_admin_session)])
async def close_position(req: ClosePositionRequest):
    """Manually close a specific open position (Superadmin only)."""
    adapter = order_router.get_adapter(req.venue)
    try:
        res = await adapter.close_position(req.symbol, req.side, req.size)
        return {"status": "success", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share/create")
async def create_position_share(
    req: CreatePositionShareRequest,
    session_payload=Depends(get_optional_session)
):
    """
    Generate an authenticated or public share token for a specific position.
    Strictly masks sensitive account data and private balances.
    """
    username = session_payload.get("username", "vip_member") if session_payload else "trader_quant"
    try:
        record = position_share_manager.create_share(
            username=username,
            symbol=req.symbol,
            side=req.side,
            leverage=req.leverage,
            entry_price=req.entry_price,
            mark_price=req.mark_price,
            unrealized_pnl_ratio=req.unrealized_pnl_ratio,
            venue=req.venue,
            council_insight=req.council_insight or "",
            custom_alias=req.custom_alias
        )
        return {"status": "success", "share": record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share/{share_id}")
async def get_position_share(share_id: str):
    """
    Public open showcase endpoint for a shared position.
    Accessible without credentials, exclusively exposes designated position track metrics.
    """
    record = position_share_manager.get_share(share_id)
    if not record:
        raise HTTPException(status_code=404, detail="该仓位分享链接不存在或已过期失效")
    return {"status": "success", "share": record}


@router.get("/shares")
async def list_position_shares(session_payload=Depends(get_optional_session)):
    """List recent share records."""
    username = session_payload.get("username") if session_payload else None
    return {"status": "success", "shares": position_share_manager.list_shares(username)}

